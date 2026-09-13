# Discord-Bot für VerifyLink

Nimmt den Verifizierungscode entgegen und reicht ihn an das
Minecraft-Plugin weiter.

## Ablauf

```
Spieler im Spiel:    /verify           →  bekommt einen Code
Spieler im Discord:  /verify <code>    →  Bot ruft POST /api/v1/verify auf
                                       →  verknüpft, Rolle wird vergeben
```

Der Bot **stellt keine Codes aus** — das macht das Plugin. Und er hat
**keinen Datenbankzugriff**: alles läuft über die Schnittstelle, nur das
Plugin schreibt.

## Aufbau

```
main.py                        Start
bot/config.py                  Konfiguration aus Umgebungsvariablen
bot/client.py                  Discord-Anbindung, lädt die Cogs
bot/cogs/link.py               der Befehl /verify
bot/services/verifylink_api.py Client für die REST-Schnittstelle
bot/logging_setup.py           Protokollierung, hält Geheimnisse raus
```

Rund 700 Zeilen. Der einzige Befehl ist `/verify <code>`; die Antwort ist
nur für den Aufrufer sichtbar, weil der Code ein Geheimnis ist.

## Einrichtung

1. `cp .env.example .env` und ausfüllen. Nötig sind mindestens
   `DISCORD_TOKEN` und `VERIFYLINK_API_TOKEN` — letzterer muss mit
   `api.token` aus der `config.yml` des Plugins übereinstimmen.

2. Starten:

   ```bash
   pip install -r requirements.txt
   python main.py
   ```

   Oder im Container: das `Dockerfile` liegt bei.

Beim Start prüft der Bot die Schnittstelle und meldet
`VerifyLink erreichbar (Datenbank: up)`. Kommt er nicht dran, sagt er das —
`/verify` antwortet dann mit einer verständlichen Störungsmeldung statt
ins Leere zu laufen.

## Fehlermeldungen

Die Kennungen kommen vom Plugin und sind in dessen `API.md` festgelegt.
`bot/cogs/link.py` übersetzt sie in Sätze für den Nutzer:

| Kennung | was der Nutzer liest |
|---|---|
| `CODE_NOT_FOUND` | Code gibt es nicht, im Spiel einen neuen holen |
| `CODE_EXPIRED` | abgelaufen, im Spiel einen neuen holen |
| `CODE_ALREADY_USED` | schon benutzt, jeder gilt einmal |
| `MINECRAFT_ALREADY_LINKED` | Minecraft-Account gehört schon jemandem |
| `DISCORD_ALREADY_LINKED` | du bist bereits verknüpft |
| `MALFORMED_REQUEST` | Code sieht falsch aus (nie **O**, **I**, **0**, **1**) |
| `SERVICE_UNAVAILABLE` | gerade nicht erreichbar |

Wiederholte Aufrufe sind gefahrlos: Die Schnittstelle antwortet auf einen
erneuten Versuch mit denselben Angaben wieder mit `200` und derselben
Verknüpfung.

## Der Token

Das Plugin kann **nicht** prüfen, ob die `discordId` in einem Aufruf zu der
Person gehört, die den Code getippt hat — es vertraut dem Bot vollständig.
Wer den Token besitzt, kann jede beliebige Discord-ID an jeden gültigen Code
binden. Entsprechend behandeln.
