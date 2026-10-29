# ICF-MCP-Server

MCP-Server für die deutsche ICF auf Basis von `../icf_json` (`icf_flat.json`, `qualifiers.json`).
Keine Abhängigkeiten – nur Node.js ≥ 18.

## Tools

| Tool | Zweck |
| --- | --- |
| `icf_search` | Volltextsuche in Titeln, Beschreibungen, Einschlüssen (auch Code-Präfixe) |
| `icf_get_code` | Titel, Beschreibung, Ein-/Ausschlüsse, Hierarchiepfad, Unterkategorien |
| `icf_list_chapters` | Komponenten b/s/d/e mit Kapiteln |
| `icf_get_related` | Eltern, Geschwister, Kinder, über Ausschlüsse verknüpfte Codes |
| `icf_get_qualifiers` | Beurteilungsmerkmale und Werteskala für einen Code |
| `icf_interpret_coding` | Prüft und übersetzt z. B. `d450.23`, `e310+3`, `s7500.213` |

## Einbinden

Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
"mcpServers": {
  "icf": { "command": "/opt/homebrew/bin/node", "args": ["/pfad/zu/icf-api/mcp/server.mjs"] }
}
```

Claude Code:

```bash
claude mcp add --scope user icf -- node /pfad/zu/icf-api/mcp/server.mjs
```

## Daten aktualisieren

`./run_icf_workflow.sh` erzeugt `icf_json/` inklusive `qualifiers.json` neu aus der ClaML-XML.
