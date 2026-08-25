#!/usr/bin/env python3
import json
import sqlite3
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "dilbar.db"
PORT = 3000


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS store (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            stock TEXT NOT NULL DEFAULT '[]',
            sales TEXT NOT NULL DEFAULT '[]',
            debts TEXT NOT NULL DEFAULT '[]',
            updated_at TEXT NOT NULL
        )
        """
    )
    row = conn.execute("SELECT id FROM store WHERE id = 1").fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO store (id, stock, sales, debts, updated_at) VALUES (1, '[]', '[]', '[]', datetime('now'))"
        )
        conn.commit()
    return conn


def parse_list(raw):
    try:
        value = json.loads(raw)
        return value if isinstance(value, list) else []
    except json.JSONDecodeError:
        return []


def read_store(conn):
    stock, sales, debts = conn.execute(
        "SELECT stock, sales, debts FROM store WHERE id = 1"
    ).fetchone()
    return {
        "stock": parse_list(stock),
        "sales": parse_list(sales),
        "debts": parse_list(debts),
    }


def write_store(conn, payload):
    stock = payload.get("stock") if isinstance(payload.get("stock"), list) else []
    sales = payload.get("sales") if isinstance(payload.get("sales"), list) else []
    debts = payload.get("debts") if isinstance(payload.get("debts"), list) else []
    conn.execute(
        """
        UPDATE store
        SET stock = ?, sales = ?, debts = ?, updated_at = datetime('now')
        WHERE id = 1
        """,
        (json.dumps(stock, ensure_ascii=False), json.dumps(sales, ensure_ascii=False), json.dumps(debts, ensure_ascii=False)),
    )
    conn.commit()
    return read_store(conn)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/api/store":
            conn = get_connection()
            try:
                self._send_json(200, read_store(conn))
            finally:
                conn.close()
            return
        super().do_GET()

    def do_PUT(self):
        if self.path.split("?", 1)[0] != "/api/store":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
            if not isinstance(payload, dict):
                raise ValueError("expected object")
        except (json.JSONDecodeError, ValueError):
            self._send_json(400, {"error": "invalid json"})
            return
        conn = get_connection()
        try:
            self._send_json(200, write_store(conn, payload))
        finally:
            conn.close()

    def log_message(self, format, *args):
        print("%s - %s" % (self.address_string(), format % args))


if __name__ == "__main__":
    get_connection().close()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"dilbar.luxe: http://127.0.0.1:{PORT}", flush=True)
    print(f"SQLite: {DB_PATH}", flush=True)
    server.serve_forever()
