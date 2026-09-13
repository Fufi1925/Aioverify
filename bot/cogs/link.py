"""Der Verifizierungsbefehl.

Der Ablauf: Der Spieler tippt **im Spiel** ``/verify`` und bekommt dort
seinen Code. Hier gibt er ihn ein, der Bot reicht ihn an das Plugin weiter.
Der Bot stellt selbst keine Codes aus.
"""

from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

log = logging.getLogger(__name__)

FARBE_OK = discord.Colour(0x3BA55D)
FARBE_FEHLER = discord.Colour(0xED4245)
FARBE_HINWEIS = discord.Colour(0xFAA61A)

#: Was der Nutzer bei welcher Fehlerkennung lesen soll. Die Kennungen
#: stammen aus API.md und sind der Vertrag mit dem Plugin.
MELDUNGEN: dict[str, tuple[str, str]] = {
    "CODE_NOT_FOUND": (
        "Diesen Code gibt es nicht",
        "Tippe im Spiel `/verify`, um einen neuen zu bekommen.\n"
        "Achte darauf: der Code enthaelt nie **O**, **I**, **0** oder **1**.",
    ),
    "CODE_EXPIRED": (
        "Der Code ist abgelaufen",
        "Codes gelten nur wenige Minuten. Hol dir im Spiel mit `/verify` einen neuen.",
    ),
    "CODE_ALREADY_USED": (
        "Dieser Code wurde bereits benutzt",
        "Jeder Code gilt genau einmal. Im Spiel `/verify` tippen fuer einen neuen.",
    ),
    "MINECRAFT_ALREADY_LINKED": (
        "Dieser Minecraft-Account ist schon vergeben",
        "Er gehoert bereits zu einem anderen Discord-Account. "
        "Melde dich beim Team, wenn das nicht stimmt.",
    ),
    "DISCORD_ALREADY_LINKED": (
        "Du bist bereits verknuepft",
        "Dein Discord-Account haengt schon an einem Minecraft-Account.",
    ),
    "MALFORMED_REQUEST": (
        "Der Code sieht nicht richtig aus",
        "Er besteht aus sechs Zeichen und enthaelt nie **O**, **I**, **0** oder **1**.",
    ),
    "RATE_LIMITED": (
        "Zu viele Versuche",
        "Bitte warte einen Moment und versuche es dann erneut.",
    ),
    "SERVICE_UNAVAILABLE": (
        "Gerade nicht erreichbar",
        "Die Verifizierung pausiert kurz. Bitte versuche es in ein paar Minuten erneut.",
    ),
    "UNAUTHORIZED": (
        "Fehler in der Einrichtung",
        "Der Bot darf nicht auf die Verifizierung zugreifen. Bitte dem Team melden.",
    ),
}

STANDARD = (
    "Das hat nicht geklappt",
    "Bitte versuche es gleich noch einmal.",
)


class LinkCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.config = bot.config
        self.api = bot.verifylink

    @app_commands.command(
        name="verify",
        description="Loese den Code ein, den du im Spiel mit /verify bekommen hast.",
    )
    @app_commands.describe(code="Der Code aus dem Spiel, z. B. K7M2QX")
    async def verify(self, interaction: discord.Interaction, code: str) -> None:
        # Nur fuer den Aufrufer sichtbar: der Code ist ein Geheimnis und
        # hat in einem oeffentlichen Kanal nichts verloren.
        await interaction.response.defer(ephemeral=True, thinking=True)

        ergebnis = await self.api.redeem(
            code=code,
            discord_id=interaction.user.id,
            discord_username=interaction.user.name,
        )

        if ergebnis.ok and ergebnis.account:
            await interaction.followup.send(
                embed=self._erfolg(ergebnis.account), ephemeral=True)
            await self._rolle_vergeben(interaction)
            log.info("Verknuepft: %s (%s) <-> %s",
                     ergebnis.account.minecraft_name,
                     ergebnis.account.minecraft_uuid, interaction.user.id)
            return

        titel, text = MELDUNGEN.get(ergebnis.error or "", STANDARD)
        if ergebnis.error == "RATE_LIMITED" and ergebnis.retry_after:
            text = f"Bitte warte noch {ergebnis.retry_after} Sekunden."

        embed = discord.Embed(
            title=f"\N{CROSS MARK} {titel}",
            description=text,
            colour=FARBE_HINWEIS if ergebnis.error in (
                "DISCORD_ALREADY_LINKED", "RATE_LIMITED") else FARBE_FEHLER,
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    def _erfolg(self, konto) -> discord.Embed:
        embed = discord.Embed(
            title="\N{WHITE HEAVY CHECK MARK} Verifiziert",
            description=(
                f"Dein Discord-Account ist jetzt mit "
                f"**{konto.minecraft_name}** verknuepft."
            ),
            colour=FARBE_OK,
        )
        embed.set_thumbnail(url=konto.head_url)
        embed.add_field(name="Minecraft", value=f"`{konto.minecraft_name}`", inline=True)
        embed.add_field(name="UUID", value=f"`{konto.minecraft_uuid}`", inline=False)
        return embed

    async def _rolle_vergeben(self, interaction: discord.Interaction) -> None:
        """Vergibt die verifiziert-Rolle, falls eine eingerichtet ist."""
        rollen_id = self.config.verified_role_id
        if not rollen_id or interaction.guild is None:
            return

        rolle = interaction.guild.get_role(rollen_id)
        if rolle is None:
            log.warning("VERIFIED_ROLE_ID %s existiert auf diesem Server nicht.",
                        rollen_id)
            return

        mitglied = interaction.user
        if not isinstance(mitglied, discord.Member):
            try:
                mitglied = await interaction.guild.fetch_member(interaction.user.id)
            except discord.HTTPException:
                return

        if rolle in mitglied.roles:
            return

        try:
            await mitglied.add_roles(rolle, reason="Minecraft-Verifizierung")
            log.info("Rolle '%s' an %s vergeben.", rolle.name, mitglied.id)
        except discord.Forbidden:
            log.error("Keine Berechtigung fuer die Rolle '%s'. Die Bot-Rolle muss in "
                      "der Rangfolge UEBER ihr stehen.", rolle.name)
        except discord.HTTPException as exc:
            log.error("Rollenvergabe fehlgeschlagen: %s", exc)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LinkCog(bot))
