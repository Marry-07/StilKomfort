import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
CART_TYPE = "application/x-furniture-cart"


class FurnitureStoreTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build = tempfile.TemporaryDirectory()
        cls.addClassCleanup(build.cleanup)
        subprocess.run(
            [shutil.which("javac") or "javac", "-encoding", "UTF-8", "-d", build.name, "Main.java"],
            cwd=ROOT,
            check=True,
            timeout=30,
        )
        java_in_path = shutil.which("java") or "java"
        settings = subprocess.check_output(
            [java_in_path, "-XshowSettings:properties", "-version"],
            stderr=subprocess.STDOUT, text=True, timeout=15,
        )
        java_home = next(line.split("=", 1)[1].strip() for line in settings.splitlines()
                         if line.strip().startswith("java.home ="))
        java_name = "java.exe" if os.name == "nt" else "java"
        cls.commands = {
            "Python": [sys.executable, "app.py"],
            "Java": [
                str(Path(java_home) / "bin" / java_name),
                "-Dstdout.encoding=UTF-8",
                "-Dstderr.encoding=UTF-8",
                "-cp", build.name, "Main",
            ],
        }

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.database = Path(directory.name) / "продажи.db"

    def environment(self):
        return {
            **os.environ,
            "FURNITURE_DB": str(self.database),
            "FURNITURE_PORT": "0",
            "PYTHONIOENCODING": "utf-8",
        }

    @contextmanager
    def server(self, language):
        log_path = self.database.parent / f"{language}.log"
        with log_path.open("wb") as log, subprocess.Popen(
            self.commands[language],
            cwd=ROOT,
            env=self.environment(),
            stdout=log,
            stderr=subprocess.STDOUT,
        ) as process:
            try:
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline and process.poll() is None:
                    output = log_path.read_text(encoding="utf-8", errors="replace")
                    address = next((line for line in output.splitlines()
                                    if line.startswith("http://127.0.0.1:")), None)
                    if address:
                        yield address
                        return
                    time.sleep(0.05)
                self.fail(f"{language}: {log_path.read_text(encoding='utf-8', errors='replace')}")
            finally:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=10)

    def request(self, address, path, cart=None, *, content_type=CART_TYPE):
        headers = {} if cart is None else {"Content-Type": content_type}
        body = None if cart is None else cart.encode("utf-8")
        request = Request(address + path, data=body, headers=headers)
        try:
            response = urlopen(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            payload = response.read()
            if response.headers.get_content_type() == "application/json":
                payload = json.loads(payload)
            return response.status, payload

    def query(self, sql):
        with closing(sqlite3.connect(self.database)) as connection, connection:
            return connection.execute(sql).fetchall()

    def test_web_page_and_assets(self):
        for language in self.commands:
            with self.subTest(language=language), self.server(language) as address:
                status, html = self.request(address, "/")
                self.assertEqual(status, 200)
                self.assertIn(b'<div id="app"></div>', html)
                bundles = re.findall(r'(?:src|href)="(/assets/[^"]+\.(?:css|js))"', html.decode())
                self.assertEqual({Path(path).suffix for path in bundles}, {".js", ".css"})
                photos = sorted((ROOT / "web" / "public" / "images").glob("*.webp"))
                self.assertEqual(len(photos), 26)
                for path in [*bundles, *(f"/images/{photo.name}" for photo in photos)]:
                    status, body = self.request(address, path)
                    self.assertEqual(status, 200, path)
                    self.assertGreater(len(body), 100, path)
                self.assertEqual(self.request(address, "/schema.sql")[0], 404)

    def test_catalog_and_empty_history(self):
        for language in ("Java", "Python"):
            with self.subTest(language=language), self.server(language) as address:
                status, products = self.request(address, "/api/products")
                self.assertEqual(status, 200)
                self.assertEqual([product["id"] for product in products], list(range(1, 26)))
                self.assertEqual(products[0], {"id": 1, "name": "Стул «Лофт»", "price": 3500, "stock": 10})
                self.assertEqual(self.request(address, "/api/sales"), (200, []))

    def test_database_open_failure_is_reported(self):
        self.database = self.database.parent / "missing" / self.database.name
        for language, command in self.commands.items():
            with self.subTest(language=language):
                result = subprocess.run(
                    command, cwd=ROOT, env=self.environment(),
                    capture_output=True, encoding="utf-8", timeout=15,
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn("Ошибка запуска", result.stdout + result.stderr)

    def test_multiple_items_and_repeated_code(self):
        for language in self.commands:
            with self.subTest(language=language), self.server(language) as address:
                status, receipt = self.request(address, "/api/sales", "1:2 2:1 1:1")
                self.assertEqual((status, receipt["total"]), (201, 23000))
        self.assertEqual(self.query("SELECT id, stock FROM products WHERE id <= 4 ORDER BY id"),
                         [(1, 4), (2, 3), (3, 3), (4, 4)])
        self.assertEqual(
            self.query("SELECT sale_id, product_id, quantity, unit_price FROM sale_items ORDER BY sale_id, product_id"),
            [(1, 1, 3, 3500), (1, 2, 1, 12500), (2, 1, 3, 3500), (2, 2, 1, 12500)],
        )

    def test_insufficient_stock_rolls_back_all_items(self):
        for language in self.commands:
            with self.subTest(language=language), self.server(language) as address:
                status, failure = self.request(address, "/api/sales", "1:2 2:6")
                self.assertEqual(status, 409)
                self.assertIn("Товаров не хватает", failure["error"])
                self.assertEqual(self.query("SELECT stock FROM products WHERE id = 1"), [(10,)])
                self.assertEqual(self.query("SELECT * FROM sales"), [])
                self.assertEqual(self.query("SELECT * FROM sale_items"), [])

    def test_missing_product_rolls_back_and_seller_can_retry(self):
        for language in self.commands:
            with self.subTest(language=language), self.server(language) as address:
                status, failure = self.request(address, "/api/sales", "1:2 99:1")
                self.assertEqual(status, 409)
                self.assertIn("Товар отсутствует", failure["error"])
                status, receipt = self.request(address, "/api/sales", "1:1")
                self.assertEqual((status, receipt["total"]), (201, 3500))
        self.assertEqual(self.query("SELECT stock FROM products WHERE id = 1"), [(8,)])
        self.assertEqual(self.query("SELECT COUNT(*) FROM sales"), [(2,)])

    def test_invalid_input(self):
        for language in self.commands:
            with self.subTest(language=language), self.server(language) as address:
                for body in ("1:0", "abc", "1:2147483647 1:1", "", "1:1 " * 1025):
                    self.assertEqual(self.request(address, "/api/sales", body)[0], 400)
                self.assertEqual(self.request(address, "/api/sales", "1:1", content_type="text/plain")[0], 415)
        self.assertEqual(self.query("SELECT * FROM sales"), [])

    def test_shared_history_and_fixed_sale_price(self):
        with self.server("Python") as python, self.server("Java") as java:
            self.assertEqual(self.request(python, "/api/sales", "1:1"), (201, {"id": 1, "total": 3500}))
            self.query("UPDATE products SET price = 4000 WHERE id = 1")
            status, history = self.request(java, "/api/sales")
            self.assertEqual((status, history[0]["total"]), (200, 3500))
            self.assertTrue(history[0]["createdAt"].endswith("Z"))
            self.assertEqual(self.request(java, "/api/sales", "1:1"), (201, {"id": 2, "total": 4000}))
            self.assertEqual(self.request(python, "/api/products")[1][0]["stock"], 8)
            self.assertEqual([sale["total"] for sale in self.request(python, "/api/sales")[1]], [4000, 3500])

    def test_competing_sales_do_not_oversell(self):
        with self.server("Python") as python, self.server("Java") as java:
            with ThreadPoolExecutor(max_workers=2) as executor:
                outcomes = list(executor.map(lambda address: self.request(address, "/api/sales", "3:3"), (python, java)))
        self.assertEqual(sorted(status for status, _ in outcomes), [201, 409])
        self.assertEqual(self.query("SELECT stock FROM products WHERE id = 3"), [(0,)])
        self.assertEqual(self.query("SELECT COUNT(*) FROM sales"), [(1,)])


if __name__ == "__main__":
    unittest.main()
