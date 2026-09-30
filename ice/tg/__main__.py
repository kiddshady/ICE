"""El bot de verdad: `python -m ice.tg`.

Lee la configuración de un archivo `.env` en la carpeta de ICE (ver
`.env.example`). El token nunca va al repo: `.env` está en el .gitignore.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from aiogram import Bot
from aiogram.utils.token import TokenValidationError

from .bot import ICE, log

ROOT = Path(__file__).resolve().parents[2]


def load_env(path: Path) -> None:
    """Un .env mínimo: líneas CLAVE=valor, # para comentarios. Lo que ya está
    en el entorno gana, así se puede pisar sin tocar el archivo."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and not key.startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def main() -> int:
    # Nombres de grupos y personas traen emojis: que la consola de Windows no
    # se caiga si la salida va a un archivo.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    load_env(ROOT / ".env")
    token = os.environ.get("ICE_TOKEN", "")
    if not token:
        print("Falta el token. Copiá .env.example como .env y poné ICE_TOKEN "
              "(te lo da @BotFather).")
        return 1
    notify_chat = os.environ.get("ICE_NOTIFY_CHAT", "").strip()
    try:
        bot = Bot(token)
    except TokenValidationError:
        print("El token de ICE_TOKEN no tiene la forma de un token de @BotFather.")
        return 1
    ice = ICE(bot, ROOT / "data", int(notify_chat) if notify_chat else None)
    try:
        asyncio.run(ice.run())
    except KeyboardInterrupt:
        log("Cortado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
