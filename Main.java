import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.StringJoiner;
import java.util.concurrent.Executors;
import java.util.stream.Collectors;

public class Main {
    private static final Path WEB = Path.of("web", "dist").toAbsolutePath().normalize();
    private static final String CART_TYPE = "application/x-furniture-cart";
    private static final String INVALID_CART = "Укажите товары и положительное количество.";
    private final FurnitureStore store;

    Main(FurnitureStore store) {
        this.store = store;
    }

    public static void main(String[] args) {
        try {
            String databasePath = System.getenv().getOrDefault("FURNITURE_DB", "furniture.db");
            SqliteDatabase database = new SqliteDatabase(databasePath);
            database.execute(Files.readString(Path.of("schema.sql")));
            int port = Integer.parseInt(System.getenv().getOrDefault("FURNITURE_PORT", "8000"));
            HttpServer server = HttpServer.create(new InetSocketAddress("127.0.0.1", port), 0);
            server.createContext("/", new Main(new FurnitureStore(database))::handle);
            server.setExecutor(Executors.newVirtualThreadPerTaskExecutor());
            server.start();
            System.out.println("http://127.0.0.1:" + server.getAddress().getPort());
            System.out.flush();
        } catch (IOException | IllegalArgumentException | IllegalStateException error) {
            System.err.println("Ошибка запуска: " + error.getMessage());
            System.exit(1);
        }
    }

    private void handle(HttpExchange request) throws IOException {
        try {
            String path = request.getRequestURI().getPath();
            switch (request.getRequestMethod()) {
                case "GET" -> get(request, path);
                case "POST" -> {
                    if (path.equals("/api/sales")) {
                        sell(request);
                    } else {
                        error(request, 404, "Страница не найдена.");
                    }
                }
                default -> error(request, 405, "Метод не поддерживается.");
            }
        } catch (IllegalStateException failure) {
            System.err.println(failure.getMessage());
            error(request, 500, "Не удалось загрузить данные.");
        } finally {
            request.close();
        }
    }

    private void get(HttpExchange request, String path) throws IOException {
        if (path.equals("/api/products")) {
            String products = store.catalog().stream()
                    .map(product -> "{\"id\":" + product.id() + ",\"name\":" + quote(product.name())
                            + ",\"price\":" + product.price() + ",\"stock\":" + product.stock() + "}")
                    .collect(Collectors.joining(",", "[", "]"));
            json(request, 200, products);
            return;
        }
        if (path.equals("/api/sales")) {
            String sales = store.history().stream()
                    .map(sale -> "{\"id\":" + sale.id() + ",\"createdAt\":" + quote(sale.createdAt())
                            + ",\"quantity\":" + sale.quantity() + ",\"total\":" + sale.total() + "}")
                    .collect(Collectors.joining(",", "[", "]"));
            json(request, 200, sales);
            return;
        }
        Path asset = WEB.resolve(path.equals("/") ? "index.html" : path.substring(1)).normalize();
        if (!asset.startsWith(WEB) || !Files.isRegularFile(asset)) {
            error(request, 404, "Страница не найдена.");
            return;
        }
        String name = asset.getFileName().toString();
        String type = switch (name.substring(name.lastIndexOf('.') + 1)) {
            case "html" -> "text/html; charset=utf-8";
            case "css" -> "text/css; charset=utf-8";
            case "js" -> "text/javascript; charset=utf-8";
            case "webp" -> "image/webp";
            case "jpeg", "jpg" -> "image/jpeg";
            case "png" -> "image/png";
            case "woff2" -> "font/woff2";
            default -> "application/octet-stream";
        };
        reply(request, 200, type, Files.readAllBytes(asset));
    }

    private void sell(HttpExchange request) throws IOException {
        if (!CART_TYPE.equals(request.getRequestHeaders().getFirst("Content-Type"))) {
            error(request, 415, "Неподдерживаемый формат запроса.");
            return;
        }
        byte[] body = request.getRequestBody().readNBytes(4097);
        if (body.length == 0 || body.length > 4096) {
            error(request, 400, INVALID_CART);
            return;
        }
        try {
            Map<Integer, Integer> cart = parseCart(new String(body, StandardCharsets.UTF_8));
            Receipt receipt = store.sell(cart);
            json(request, 201, "{\"id\":" + receipt.id() + ",\"total\":" + receipt.total() + "}");
        } catch (NumberFormatException | ArithmeticException failure) {
            error(request, 400, INVALID_CART);
        } catch (IllegalStateException failure) {
            String reason = failure.getMessage();
            if (reason.contains("PRODUCT_NOT_FOUND")) {
                error(request, 409, "Товар отсутствует в каталоге.");
            } else if (reason.contains("INSUFFICIENT_STOCK")) {
                error(request, 409, "Товаров не хватает. Проверьте остатки.");
            } else {
                System.err.println(reason);
                error(request, 500, "Не удалось оформить продажу.");
            }
        }
    }

    private static Map<Integer, Integer> parseCart(String text) {
        Map<Integer, Integer> cart = new LinkedHashMap<>();
        for (String item : text.strip().split("(?U)\\s+")) {
            if (!item.matches("[0-9]+:[0-9]+")) {
                throw new NumberFormatException();
            }
            String[] parts = item.split(":");
            int productId = Integer.parseInt(parts[0]);
            int quantity = Integer.parseInt(parts[1]);
            if (productId <= 0 || quantity <= 0) {
                throw new NumberFormatException();
            }
            cart.merge(productId, quantity, Math::addExact);
        }
        return cart;
    }

    private static String quote(String value) {
        StringBuilder escaped = new StringBuilder("\"");
        for (char character : value.toCharArray()) {
            if (character == '"' || character == '\\') {
                escaped.append('\\').append(character);
            } else if (character < ' ') {
                escaped.append("\\u%04x".formatted((int) character));
            } else {
                escaped.append(character);
            }
        }
        return escaped.append('"').toString();
    }

    private static void error(HttpExchange request, int status, String message) throws IOException {
        json(request, status, "{\"error\":" + quote(message) + "}");
    }

    private static void json(HttpExchange request, int status, String body) throws IOException {
        reply(request, status, "application/json; charset=utf-8", body.getBytes(StandardCharsets.UTF_8));
    }

    private static void reply(HttpExchange request, int status, String type, byte[] body) throws IOException {
        request.getResponseHeaders().set("Content-Type", type);
        request.getResponseHeaders().set("Cache-Control", "no-store");
        request.sendResponseHeaders(status, body.length);
        request.getResponseBody().write(body);
    }
}

record Product(long id, String name, long price, long stock) {}
record Sale(long id, String createdAt, long quantity, long total) {}
record Receipt(long id, long total) {}

class FurnitureStore {
    private final SqliteDatabase database;

    FurnitureStore(SqliteDatabase database) {
        this.database = database;
    }

    List<Product> catalog() {
        return database.rows("SELECT id, hex(name), price, stock FROM products ORDER BY id;")
                .stream()
                .map(row -> new Product(Long.parseLong(row[0]),
                        new String(HexFormat.of().parseHex(row[1]), StandardCharsets.UTF_8),
                        Long.parseLong(row[2]), Long.parseLong(row[3])))
                .toList();
    }

    List<Sale> history() {
        return database.rows("SELECT id, created_at, quantity, total FROM sale_totals ORDER BY id DESC;")
                .stream()
                .map(row -> new Sale(Long.parseLong(row[0]), row[1].replace(' ', 'T') + "Z",
                        Long.parseLong(row[2]), Long.parseLong(row[3])))
                .toList();
    }

    Receipt sell(Map<Integer, Integer> cart) {
        StringJoiner rows = new StringJoiner(",\n");
        for (Map.Entry<Integer, Integer> item : cart.entrySet()) {
            // В SQL подставляются только целые числа, проверенные при вводе.
            rows.add("(" + item.getKey() + ", " + item.getValue() + ")");
        }

        // Таблица sale_items создана WITHOUT ROWID, поэтому last_insert_rowid() хранит номер продажи.
        String[] result = database.rows("""
                BEGIN IMMEDIATE;
                INSERT INTO sales DEFAULT VALUES;
                WITH cart(product_id, quantity) AS (VALUES %s)
                INSERT INTO sale_items (sale_id, product_id, quantity, unit_price)
                SELECT last_insert_rowid(), cart.product_id, cart.quantity, products.price
                FROM cart LEFT JOIN products ON products.id = cart.product_id;
                SELECT id, total FROM sale_totals WHERE id = last_insert_rowid();
                COMMIT;
                """.formatted(rows)).getFirst();
        return new Receipt(Long.parseLong(result[0]), Long.parseLong(result[1]));
    }
}

class SqliteDatabase {
    private static final String SEPARATOR = "\u001f";
    private final String openDatabase;

    SqliteDatabase(String path) {
        String escapedPath = Path.of(path).toAbsolutePath().toString()
                .replace("\\", "\\\\").replace("\"", "\\\"")
                .replace("\r", "\\r").replace("\n", "\\n");
        // Путь передаётся через поток UTF-8, чтобы sqlite3 на Windows мог прочитать кириллицу.
        openDatabase = ".open \"" + escapedPath + "\"\n.timeout 5000\nPRAGMA foreign_keys = ON;\n";
    }

    List<String[]> rows(String sql) {
        return execute(sql).lines().map(line -> line.split(SEPARATOR, -1)).toList();
    }

    String execute(String sql) {
        try {
            Process process = new ProcessBuilder(
                    "sqlite3", "-batch", "-bail", "-noheader", "-list",
                    "-separator", SEPARATOR)
                    .redirectErrorStream(true)
                    .start();
            try (var stdin = process.getOutputStream()) {
                stdin.write((openDatabase + sql + "\n").getBytes(StandardCharsets.UTF_8));
            }
            String output = new String(process.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
            // При ошибке .open утилита может переключиться на временную базу и вернуть код 0.
            if (process.waitFor() != 0 || output.startsWith("Error:")) {
                throw new IllegalStateException(output.strip());
            }
            return output;
        } catch (IOException error) {
            throw new IllegalStateException("Не удалось выполнить команду sqlite3. " + error.getMessage(), error);
        } catch (InterruptedException error) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("Операция прервана.", error);
        }
    }
}
