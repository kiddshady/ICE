"""Servidor del simulador: `python -m ice.sim` y abrí http://127.0.0.1:4390
(o `python -m ice.sim <puerto>` para usar otro).

Sirve la página y una sola ruta, POST /api, que le pasa cada pedido a la
sesión. Usa solo la librería estándar de Python: no hay nada que instalar.
"""
from __future__ import annotations

import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .session import Session

HOST, PORT = "127.0.0.1", 4390
STATIC = Path(__file__).parent / "static"
TYPES = {".html": "text/html", ".css": "text/css", ".js": "text/javascript",
         ".svg": "image/svg+xml", ".woff2": "font/woff2", ".txt": "text/plain"}

session = Session()
lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        name = "index.html" if self.path in ("/", "/index.html") else self.path.lstrip("/")
        path = (STATIC / name).resolve()
        if STATIC not in path.parents or not path.is_file():
            self.send_error(404)
            return
        self._send(path.read_bytes(), TYPES.get(path.suffix, "application/octet-stream"))

    def do_POST(self) -> None:
        if self.path != "/api":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            cmd = json.loads(self.rfile.read(length) or b"{}")
            with lock:
                result = session.handle(cmd)
        except (ValueError, KeyError) as e:
            self._send(json.dumps({"error": str(e)}).encode(), "application/json", 400)
            return
        self._send(json.dumps(result, ensure_ascii=False).encode(), "application/json")

    def _send(self, body: bytes, ctype: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        pass  # sin una línea por pedido: la página pregunta la hora cada pocos segundos


def main() -> None:
    # `python -m ice.sim 4391` lo abre en otro puerto.
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    server = ThreadingHTTPServer((HOST, port), Handler)
    print(f"Simulador de ICE en http://{HOST}:{port}  (Ctrl+C para cortar)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nListo.")
        sys.exit(0)


if __name__ == "__main__":
    main()
