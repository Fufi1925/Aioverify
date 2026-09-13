from __future__ import annotations
import asyncio
import logging
import sys

import discord

from bot.client import MCVerifyBot
from bot.config import BASE_DIR, Config, ConfigError
from bot.logging_setup import setup_logging

log = logging.getLogger("main")


def abort(message: str) -> None:
    print("\n" + "=" * 62, file=sys.stderr)
    print("  START FEHLGESCHLAGEN", file=sys.stderr)
    print("=" * 62, file=sys.stderr)
    print(message, file=sys.stderr)
    print("=" * 62 + "\n", file=sys.stderr)
    sys.exit(1)


async def run() -> None:
    try:
        config = Config.load()
    except ConfigError as exc:
        abort(str(exc))
        return

    setup_logging(
        level=config.log_level,
        log_dir=BASE_DIR / "logs",
        # Beide duerfen niemals im Protokoll auftauchen.
        secrets=[config.token, config.api_token],
    )

    log.info("Starte Discord-Minecraft-Verifizierungsbot ...")

    bot = MCVerifyBot(config)
    try:
        await bot.start(config.token)
    except discord.LoginFailure:
        abort(
            "Der DISCORD_TOKEN wurde von Discord abgelehnt.\n\n"
        )
    except discord.PrivilegedIntentsRequired:
        abort(
            "Der 'SERVER MEMBERS INTENT' ist nicht aktiviert.\n\n"
        )
    except KeyboardInterrupt:
        pass
    finally:
        if not bot.is_closed():
            await bot.close()
            


def main() -> None:
    if sys.version_info < (3, 11):
        abort(
            f"Python 3.11"
            f"(gefunden: {sys.version.split()[0]})."
        )
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nBot durch Benutzer beendet.")


if __name__ == "__main__":
    main()
