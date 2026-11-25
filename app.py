import json
import os
import re
import sqlite3
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from mimetypes import guess_type
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web" / "dist"
DATABASE = Path(os.environ.get("FURNITURE_DB", ROOT / "furniture.db"))
MAX_NUMBER = 2_147_483_647
CART_TYPE = "application/x-furniture-cart"
INVALID_CART = "Укажите товары и положительное количество."
STOCK_ERRORS = {
    "PRODUCT_NOT_FOUND": "Товар отсутствует в каталоге.",
    "INSUFFICIENT_STOCK": "Товаров не хватает. Проверьте остатки.",
}


def connect():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def parse_cart(text):
    cart = {}
    for item in text.split():
        if re.fullmatch(r"[0-9]+:[0-9]+", item) is None:
            raise ValueError
        product_id, quantity = map(int, item.split(":"))
        total_quantity = cart.get(product_id, 0) + quantity
        if not (0 < product_id <= MAX_NUMBER and 0 < quantity <= total_quantity <= MAX_NUMBER):
            raise ValueError
        cart[product_id] = total_quantity
    if not cart:
        raise ValueError
    return cart


def save_sale(connection, cart):
    with connection:
        connection.execute("BEGIN IMMEDIATE")
        sale_id = connection.execute("INSERT INTO sales DEFAULT VALUES").lastrowid
        connection.executemany(
            """
            INSERT INTO sale_items (sale_id, product_id, quantity, unit_price)
            VALUES (?, ?, ?, (SELECT price FROM products WHERE id = ?))
            """,
            [(sale_id, product_id, quantity, product_id) for product_id, quantity in cart.items()],
        )
        total, = connection.execute(
            "SELECT total FROM sale_totals WHERE id = ?", (sale_id,)
        ).fetchone()
    return {"id": sale_id, "total": total}


def catalog():
    with closing(connect()) as connection:
        return [dict(row) for row in connection.execute(
            "SELECT id, name, price, stock FROM products ORDER BY id"
        )]


def history():
    with closing(connect()) as connection:
        return [dict(row) for row in connection.execute(
            """
            SELECT id, replace(created_at, ' ', 'T') || 'Z' AS createdAt, quantity, total
            FROM sale_totals ORDER BY id DESC
            """
        )]


class WebHandler(BaseHTTPRequestHandler):
    def reply(self, status, content_type, body):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.reply(status, "application/json; charset=utf-8", body)

    def do_GET(self):
        path = urlsplit(self.path).path
        try:
            if path == "/api/products":
                self.json(200, catalog())
                return
            if path == "/api/sales":
                self.json(200, history())
                return
            asset = (WEB / (path.lstrip("/") or "index.html")).resolve()
            if asset.is_relative_to(WEB) and asset.is_file():
                content_type = guess_type(asset.name)[0] or "application/octet-stream"
                if content_type.startswith("text/") or content_type == "application/javascript":
                    content_type += "; charset=utf-8"
                self.reply(200, content_type, asset.read_bytes())
                return
            self.json(404, {"error": "Страница не найдена."})
        except (OSError, sqlite3.Error) as error:
            self.log_error("%s", error)
            self.json(500, {"error": "Не удалось загрузить данные."})

    def do_POST(self):
        if urlsplit(self.path).path != "/api/sales":
            self.json(404, {"error": "Страница не найдена."})
            return
        if self.headers.get("Content-Type") != CART_TYPE:
            self.json(415, {"error": "Неподдерживаемый формат запроса."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4096:
                self.json(400, {"error": INVALID_CART})
                return
            cart = parse_cart(self.rfile.read(length).decode("utf-8"))
            with closing(connect()) as connection:
                self.json(201, save_sale(connection, cart))
        except ValueError:
            self.json(400, {"error": INVALID_CART})
        except sqlite3.Error as error:
            if str(error) in STOCK_ERRORS:
                self.json(409, {"error": STOCK_ERRORS[str(error)]})
            else:
                self.log_error("%s", error)
                self.json(500, {"error": "Не удалось оформить продажу."})


def main():
    try:
        with closing(connect()) as connection:
            connection.executescript((ROOT / "schema.sql").read_text(encoding="utf-8"))
        port = int(os.environ.get("FURNITURE_PORT", "8000"))
        with ThreadingHTTPServer(("127.0.0.1", port), WebHandler) as server:
            print(f"http://127.0.0.1:{server.server_port}", flush=True)
            server.serve_forever()
    except KeyboardInterrupt:
        return 0
    except (OSError, sqlite3.Error, ValueError) as error:
        print(f"Ошибка запуска: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
