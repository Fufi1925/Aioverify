"""Anbindung an die REST-Schnittstelle des VerifyLink-Plugins.

Der Bot bekommt bewusst **keinen** Datenbankzugriff. Alles laeuft ueber
diese Schnittstelle, und nur das Plugin schreibt.

Die Fehlerkennungen entsprechen API.md. Ausgewertet wird ``error`` - ein
stabiler Maschinenstring; ``message`` ist nur ein Notbehelf zur Anzeige.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import aiohttp

log = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=15)


@dataclass(slots=True)
class LinkedAccount:
    """Eine bestaetigte Verknuepfung, wie sie die Schnittstelle liefert."""

    minecraft_uuid: str
    minecraft_name: str
    discord_id: str
    discord_username: str
    linked_at: str

    @property
    def head_url(self) -> str:
        return f"https://mc-heads.net/avatar/{self.minecraft_uuid}/128"

    @property
    def body_url(self) -> str:
        return f"https://mc-heads.net/body/{self.minecraft_uuid}/128"


@dataclass(slots=True)
class ApiResult:
    """Ergebnis eines Aufrufs.

    :param ok: true bei HTTP 200
    :param account: bei Erfolg die Verknuepfung
    :param error: sonst die Fehlerkennung aus API.md
    """

    ok: bool
    account: LinkedAccount | None = None
    error: str | None = None
    retry_after: int | None = None


class VerifyLinkApi:
    """Duenner Client. Wirft nie - Fehler kommen als ``ApiResult`` zurueck."""

    def __init__(self, base_url: str, token: str) -> None:
        self._base = base_url.rstrip("/")
        self._token = token
        self._session: aiohttp.ClientSession | None = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=TIMEOUT,
                headers={"Authorization": f"Bearer {self._token}"},
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def redeem(self, code: str, discord_id: int | str,
                     discord_username: str) -> ApiResult:
        """Loest einen Code ein.

        Wiederholungen sind gefahrlos: die Schnittstelle antwortet auf einen
        erneuten Aufruf mit denselben Angaben wieder mit 200 und derselben
        Verknuepfung.
        """
        rumpf = {
            "code": code,
            "discordId": str(discord_id),
            "discordUsername": discord_username,
        }
        session = await self._ensure_session()
        try:
            async with session.post(f"{self._base}/api/v1/verify", json=rumpf) as antwort:
                if antwort.status == 200:
                    daten = await antwort.json()
                    return ApiResult(ok=True, account=LinkedAccount(
                        minecraft_uuid=daten["minecraftUuid"],
                        minecraft_name=daten["minecraftName"],
                        discord_id=daten["discordId"],
                        discord_username=daten["discordUsername"],
                        linked_at=daten["linkedAt"],
                    ))

                retry_after = None
                if antwort.status == 429:
                    try:
                        retry_after = int(antwort.headers.get("Retry-After", "0")) or None
                    except ValueError:
                        retry_after = None

                try:
                    daten = await antwort.json()
                    kennung = daten.get("error", "INTERNAL_ERROR")
                except Exception:
                    kennung = "INTERNAL_ERROR"

                # Der Code selbst wird bewusst nicht protokolliert - er ist
                # ein kurzlebiges Geheimnis.
                log.info("Einloesen abgelehnt: %s (HTTP %s)", kennung, antwort.status)
                return ApiResult(ok=False, error=kennung, retry_after=retry_after)

        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            log.warning("VerifyLink nicht erreichbar: %s", exc)
            return ApiResult(ok=False, error="SERVICE_UNAVAILABLE")

    async def health(self) -> tuple[bool, str]:
        """Zustand der Schnittstelle. Braucht keinen Token."""
        session = await self._ensure_session()
        try:
            async with session.get(f"{self._base}/api/v1/health") as antwort:
                daten = await antwort.json()
                return antwort.status == 200, daten.get("database", "unbekannt")
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            return False, str(exc)
