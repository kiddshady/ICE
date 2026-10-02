"""El bot de verdad: `python -m de4dc0dex.tg`.

Lee la configuración de un archivo `.env` en la carpeta de DE4DC0DEX (ver
`.env.example`). El token nunca va al repo: `.env` está en el .gitignore.

Con `pythonw -m de4dc0dex.tg` corre sin ventana (así lo arranca `autoarranque.ps1`
al iniciar Windows) y lo que normalmente sale en la consola va a
`data/de4dc0dex.log`.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path
from typing import IO

from aiogram import Bot
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.utils.token import TokenValidationError

from .bot import DE4DC0DEX, log

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"

# Si se cae (sin internet al prender la PC, Telegram que no contesta...),
# cuánto espera antes de volver a intentar.
RETRY_AFTER = 30

# El registro sin consola: cuando pasa de este tamaño, el viejo queda como
# de4dc0dex.log.1 y se empieza uno nuevo.
LOG_MAX = 2 * 1024 * 1024


def load_env(path: Path) -> None:
    """Un .env mínimo: líneas CLAVE=valor, # para comentarios. Lo que ya está
    en el entorno gana, así se puede pisar sin tocar el archivo."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and not key.startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def open_output() -> None:
    """Sin consola (pythonw), la salida va a data/de4dc0dex.log. Con consola, en
    UTF-8: nombres de grupos y personas traen emojis, y la consola de Windows
    no se tiene que caer si la salida va a un archivo."""
    if sys.stdout is not None:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        return
    path = DATA / "de4dc0dex.log"
    if path.is_file() and path.stat().st_size > LOG_MAX:
        os.replace(path, path.with_suffix(".log.1"))
    sys.stdout = sys.stderr = open(path, "a", encoding="utf-8", errors="replace",
                                   buffering=1)


def only_copy() -> IO | None:
    """Traba data/de4dc0dex.lock mientras el bot corre. Si ya está trabado, hay otro
    DE4DC0DEX andando: dos a la vez se pelean por los mensajes (Telegram le da cada
    uno a uno solo) y los dos moderan a medias. None si hay otro."""
    lock = open(DATA / "de4dc0dex.lock", "a+")
    try:
        if os.name == "nt":
            import msvcrt
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock.close()
        return None
    return lock


def main() -> int:
    DATA.mkdir(exist_ok=True)
    open_output()
    load_env(ROOT / ".env")
    token = os.environ.get("DE4DC0DEX_TOKEN", "")
    if not token:
        print("Falta el token. Copiá .env.example como .env y poné DE4DC0DEX_TOKEN "
              "(te lo da @BotFather).")
        return 1
    notify_chat = os.environ.get("DE4DC0DEX_NOTIFY_CHAT", "").strip()
    lock = only_copy()
    if lock is None:
        print("DE4DC0DEX ya está corriendo (seguramente el que arranca solo con Windows). "
              "Para apagarlo: .\\autoarranque.ps1 -Detener")
        return 1

    while True:
        try:
            bot = Bot(token)
        except TokenValidationError:
            print("El token de DE4DC0DEX_TOKEN no tiene la forma de un token de @BotFather.")
            return 1
        app = DE4DC0DEX(bot, DATA, int(notify_chat) if notify_chat else None)
        try:
            asyncio.run(app.run())
            return 0
        except KeyboardInterrupt:
            log("Cortado.")
            return 0
        except TelegramUnauthorizedError:
            log("Telegram no acepta el token de DE4DC0DEX_TOKEN: revisalo con @BotFather.")
            return 1
        except Exception as e:
            log(f"Se cayó: {e!r}. Vuelvo a intentar en {RETRY_AFTER} s.")
            try:
                time.sleep(RETRY_AFTER)
            except KeyboardInterrupt:
                log("Cortado.")
                return 0


if __name__ == "__main__":
    sys.exit(main())
