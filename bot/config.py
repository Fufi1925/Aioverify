"""Konfiguration des Bots.

Deutlich kuerzer als frueher: seit der Umstellung auf VerifyLink braucht
der Bot **keinen Datenbankzugriff** mehr. Alles laeuft ueber die
REST-Schnittstelle des Plugins, und nur das Plugin schreibt.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env", override=False)


def _env_str(key: str, default: str = "") -> str:
    return (os.getenv(key) or default).strip()


def _env_int(key: str, default: int) -> int:
    raw = _env_str(key)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        raise ConfigError(f"Umgebungsvariable {key}='{raw}' ist keine gueltige Zahl.")


def _env_opt_int(key: str) -> int | None:
    raw = _env_str(key).lower()
    if raw in ("", "0", "none", "null", "-"):
        return None
    try:
        return int(raw)
    except ValueError:
        raise ConfigError(f"Umgebungsvariable {key}='{raw}' ist keine gueltige ID.")


def _env_bool(key: str, default: bool = False) -> bool:
    raw = _env_str(key).lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "y", "on", "ja")


def _env_id_set(key: str) -> set[int]:
    out: set[int] = set()
    for teil in _env_str(key).replace(";", ",").split(","):
        teil = teil.strip()
        if not teil:
            continue
        try:
            out.add(int(teil))
        except ValueError:
            raise ConfigError(f"'{teil}' in {key} ist keine gueltige Discord-ID.")
    return out


class ConfigError(RuntimeError):
    pass


@dataclass(slots=True)
class Config:
    token: str

    guild_id: int | None = None
    verified_role_id: int | None = None
    log_channel_id: int | None = None
    admin_user_ids: set[int] = field(default_factory=set)

    members_intent: bool = False
    log_level: str = "INFO"

    # Zugang zum Plugin
    api_url: str = "http://velocity:8787"
    api_token: str = ""

    @classmethod
    def load(cls) -> "Config":
        token = _env_str("DISCORD_TOKEN")
        if not token:
            raise ConfigError(
                "DISCORD_TOKEN fehlt.\n"
                "  -> In der .env eintragen (cp .env.example .env)")

        api_token = _env_str("VERIFYLINK_API_TOKEN")
        if not api_token:
            raise ConfigError(
                "VERIFYLINK_API_TOKEN fehlt.\n"
                "  -> Muss mit api.token aus der config.yml des Plugins\n"
                "     uebereinstimmen (plugins/verifylink/config.yml).")

        return cls(
            token=token,
            guild_id=_env_opt_int("GUILD_ID"),
            verified_role_id=_env_opt_int("VERIFIED_ROLE_ID"),
            log_channel_id=_env_opt_int("LOG_CHANNEL_ID"),
            admin_user_ids=_env_id_set("ADMIN_USER_IDS"),
            members_intent=_env_bool("MEMBERS_INTENT", False),
            log_level=_env_str("LOG_LEVEL", "INFO").upper(),
            api_url=_env_str("VERIFYLINK_API_URL", "http://velocity:8787"),
            api_token=api_token,
        )

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_user_ids

    def safe_summary(self) -> str:
        """Zusammenfassung fuers Protokoll - ohne Token."""
        return (
            f"guild_id={self.guild_id} "
            f"verified_role={self.verified_role_id} "
            f"admins={len(self.admin_user_ids)} "
            f"members_intent={'on' if self.members_intent else 'off'} "
            f"api={self.api_url}"
        )
