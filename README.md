# ICF-MCP

MCP-Server für die deutsche **ICF** – Internationale Klassifikation der Funktionsfähigkeit, Behinderung und Gesundheit (WHO, deutsche Fassung BfArM, Stand 2005).
Damit können Claude und andere MCP-Clients ICF-Kategorien suchen, nachschlagen und Kodierungen mit Beurteilungsmerkmalen prüfen – etwa für Teilhabeplanung, Gesamtplanverfahren oder Berichte.

- Keine Abhängigkeiten, nur Node.js ≥ 18
- Läuft lokal, sendet keine Daten nach außen
- Daten: 1.495 ICF-Kategorien (b, s, d, e) inkl. Beschreibungen, Ein-/Ausschlüssen und Beurteilungsmerkmalen

## Tools

| Tool | Zweck |
| --- | --- |
| `icf_search` | Volltextsuche in Titeln, Beschreibungen und Einschlüssen; Umlaute egal, Code-Präfixe möglich, optional auf b/s/d/e eingeschränkt |
| `icf_get_code` | Titel, Beschreibung, Ein-/Ausschlüsse (mit aufgelösten Codes), Hierarchiepfad, Unterkategorien |
| `icf_list_chapters` | Komponenten b/s/d/e mit ihren Kapiteln |
| `icf_get_related` | Übergeordnete Kategorie, Geschwister, Unterkategorien, über Ausschlüsse verknüpfte Codes |
| `icf_get_qualifiers` | Notation und Werteskala der Beurteilungsmerkmale für einen Code |
| `icf_interpret_coding` | Prüft und übersetzt Kodierungen wie `d450.23`, `b1440.2`, `s7500.213`, `e310+3` |

## Installation

Repository klonen:

```bash
git clone https://github.com/politpatrick/icf-api.git ~/GitHub/icf-api
```

### Claude Desktop

In `~/Library/Application Support/Claude/claude_desktop_config.json` (oder über *Einstellungen → Entwickler → Konfiguration bearbeiten*):

```json
{
  "mcpServers": {
    "icf": {
      "command": "node",
      "args": ["/Users/<name>/GitHub/icf-api/src/server.mjs"]
    }
  }
}
```

Danach Claude Desktop komplett beenden und neu starten. Falls `node` nicht gefunden wird, den vollen Pfad angeben (`which node`, z. B. `/opt/homebrew/bin/node`).

### Claude Code

```bash
claude mcp add --scope user icf -- node ~/GitHub/icf-api/src/server.mjs
```

### Ohne Klon (direkt von GitHub)

```bash
claude mcp add --scope user icf -- npx -y github:politpatrick/icf-api
```

## Projektstruktur

```
src/                 MCP-Server
  server.mjs         Einstieg (stdio)
  protocol.mjs       JSON-RPC/MCP-Protokoll und Tool-Definitionen
  icf.mjs            Datenzugriff und Abfragelogik
icf_json/            Generierte ICF-Daten (hierarchisch, icf_flat.json, qualifiers.json)
source/              ClaML-Quelldatei der ICF
scripts/             Konvertierung ClaML → JSON
test/                Tests
```

## Entwicklung

```bash
npm test             # Tests (node:test)
npm start            # Server auf stdio starten
npm run build:data   # icf_json/ aus source/ neu erzeugen (Python 3.9+)
```

Manuell testen lässt sich der Server, indem man JSON-RPC-Zeilen auf stdin schickt:

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"icf_interpret_coding","arguments":{"coding":"d450.23"}}}' | node src/server.mjs
```

## Hinweis zu den Daten

Die ICF ist eine Klassifikation der Weltgesundheitsorganisation (WHO); die deutsche Fassung wird vom Bundesinstitut für Arzneimittel und Medizinprodukte (BfArM) herausgegeben. Die Rechte an der Klassifikation liegen bei den Herausgebern. Die Tools liefern Klassifikationsinhalte, keine fachliche Bewertung im Einzelfall.
