from __future__ import annotations

import logging
import logging.handlers
import re
import sys
from pathlib import Path

TOKEN_RE = re.compile(r"[A-Za-z0-9_\-]{24,28}\.[A-Za-z0-9_\-]{6}\.[A-Za-z0-9_\-]{27,}")
CODE_RE = re.compile(r"\bMC-\d{6}\b")


class SecretFilter(logging.Filter):
    def __init__(self, secrets: list[str] | None = None) -> None:
        super().__init__()
        self._secrets = [s for s in (secrets or []) if s and len(s) >= 8]

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True

        original = message
        for secret in self._secrets:
            message = message.replace(secret, "***REDACTED***")
        message = TOKEN_RE.sub("***TOKEN***", message)
        message = CODE_RE.sub(lambda m: m.group(0)[:5] + "****", message)

        if message != original:
            record.msg = message
            record.args = ()
        return True


class ColourFormatter(logging.Formatter):
    COLOURS = {
        logging.DEBUG: "\033[38;5;244m",
        logging.INFO: "\033[38;5;39m",
        logging.WARNING: "\033[38;5;214m",
        logging.ERROR: "\033[38;5;196m",
        logging.CRITICAL: "\033[1;38;5;196m",
    }
    RESET = "\033[0m"

    def __init__(self, use_colour: bool) -> None:
        super().__init__(
            fmt="{asctime} {levelname:<8} {name:<28} {message}",
            datefmt="%Y-%m-%d %H:%M:%S",
            style="{",
        )
        self.use_colour = use_colour

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        if not self.use_colour:
            return text
        colour = self.COLOURS.get(record.levelno, "")
        return f"{colour}{text}{self.RESET}"


def setup_logging(
    level: str = "INFO",
    log_dir: Path | None = None,
    secrets: list[str] | None = None,
) -> None:
    numeric = getattr(logging, level.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(numeric)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    secret_filter = SecretFilter(secrets)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(ColourFormatter(use_colour=sys.stdout.isatty()))
    console.addFilter(secret_filter)
    root.addHandler(console)

    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / "bot.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(
            logging.Formatter(
                "{asctime} {levelname:<8} {name:<28} {message}",
                datefmt="%Y-%m-%d %H:%M:%S",
                style="{",
            )
        )
        file_handler.addFilter(secret_filter)
        root.addHandler(file_handler)

    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
