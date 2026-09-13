from __future__ import annotations

import logging

import discord
from discord.ext import commands

from bot.config import Config
from bot.services.verifylink_api import VerifyLinkApi

log = logging.getLogger(__name__)

INITIAL_COGS = (
    "bot.cogs.link",
)


class MCVerifyBot(commands.Bot):
    """Der Bot nimmt Codes entgegen und reicht sie an das Plugin weiter.

    Er stellt selbst keine Codes aus und hat keinen Datenbankzugriff.
    """

    def __init__(self, config: Config) -> None:
        intents = discord.Intents.default()
        # Zustimmungspflichtig im Entwicklerportal. Ist er dort nicht
        # freigegeben, verweigert Discord die Anmeldung komplett - deshalb
        # abschaltbar. Die Rollenvergabe kommt auch ohne aus.
        intents.members = config.members_intent
        intents.message_content = False

        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            help_command=None,
            allowed_mentions=discord.AllowedMentions(
                everyone=False, roles=False, users=True),
        )

        self.config = config
        self.verifylink = VerifyLinkApi(config.api_url, config.api_token)

    async def setup_hook(self) -> None:
        for erweiterung in INITIAL_COGS:
            await self.load_extension(erweiterung)
            log.info("Cog geladen: %s", erweiterung)
        await self._sync_commands()

    async def _sync_commands(self) -> None:
        try:
            if self.config.guild_id:
                guild = discord.Object(id=self.config.guild_id)
                self.tree.copy_global_to(guild=guild)
                synchronisiert = await self.tree.sync(guild=guild)
                log.info("%d Slash-Command(s) fuer Guild %s: %s",
                         len(synchronisiert), self.config.guild_id,
                         ", ".join(f"/{c.name}" for c in synchronisiert))
            else:
                synchronisiert = await self.tree.sync()
                log.info("%d globale Slash-Command(s) - die Verteilung kann bis zu "
                         "einer Stunde dauern: %s", len(synchronisiert),
                         ", ".join(f"/{c.name}" for c in synchronisiert))
        except discord.HTTPException as exc:
            log.error("Slash-Commands konnten nicht synchronisiert werden: %s", exc)

    async def on_ready(self) -> None:
        assert self.user is not None
        log.info("=" * 62)
        log.info("Eingeloggt als %s (ID: %s)", self.user, self.user.id)
        log.info("Server: %d | %s", len(self.guilds), self.config.safe_summary())

        erreichbar, datenbank = await self.verifylink.health()
        if erreichbar:
            log.info("VerifyLink erreichbar (Datenbank: %s).", datenbank)
        else:
            log.warning("VerifyLink unter %s NICHT erreichbar (%s). /verify wird "
                        "bis auf Weiteres eine Stoerung melden.",
                        self.config.api_url, datenbank)

        if not self.config.verified_role_id:
            log.info("Keine VERIFIED_ROLE_ID gesetzt - es wird keine Rolle vergeben.")
        self._pruefe_rollenrangfolge()
        log.info("=" * 62)

        try:
            await self.change_presence(activity=discord.Activity(
                type=discord.ActivityType.watching, name="/verify"))
        except discord.HTTPException:
            pass

    def _pruefe_rollenrangfolge(self) -> None:
        """Warnt frueh vor dem haeufigsten Einrichtungsfehler."""
        if not (self.config.guild_id and self.config.verified_role_id):
            return
        guild = self.get_guild(self.config.guild_id)
        if guild is None:
            log.warning("Der Bot ist nicht auf dem Server mit der GUILD_ID %s.",
                        self.config.guild_id)
            return
        rolle = guild.get_role(self.config.verified_role_id)
        if rolle is None:
            log.warning("VERIFIED_ROLE_ID %s existiert auf '%s' nicht.",
                        self.config.verified_role_id, guild.name)
            return
        if guild.me.top_role <= rolle:
            log.warning("Die Bot-Rolle steht NICHT ueber '%s' - der Bot kann sie "
                        "deshalb nicht vergeben.", rolle.name)

    async def close(self) -> None:
        log.info("Bot wird beendet ...")
        try:
            await self.verifylink.close()
        except Exception:
            log.exception("Verbindung zur Schnittstelle konnte nicht sauber "
                          "geschlossen werden.")
        await super().close()
        log.info("Beendet.")
