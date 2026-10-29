// MCP-Protokoll (JSON-RPC 2.0) ohne externe Abhängigkeiten.
// Unabhängig vom Transport: handleMessage() wird von stdio- und HTTP-Einstieg genutzt.

import * as icf from "./icf.mjs";

const PROTOCOL_VERSIONS = ["2025-06-18", "2025-03-26", "2024-11-05"];

const SERVER_INFO = { name: "icf", title: "ICF (Deutsch)", version: "1.0.0" };

const INSTRUCTIONS = `Zugriff auf die deutsche ICF (Internationale Klassifikation der Funktionsfähigkeit, Behinderung und Gesundheit, WHO/BfArM 2005).
Komponenten: b = Körperfunktionen, s = Körperstrukturen, d = Aktivitäten und Partizipation, e = Umweltfaktoren.
Typischer Ablauf: icf_search findet passende Kategorien zu einer Beschreibung, icf_get_code liefert Definition, Ein-/Ausschlüsse und Unterkategorien,
icf_get_qualifiers erklärt die Beurteilungsmerkmale, icf_interpret_coding prüft und übersetzt eine vollständige Kodierung wie d450.23 oder e310+3.
Codes immer mit icf_get_code verifizieren, bevor sie in Berichten verwendet werden.`;

const codeParam = {
  type: "object",
  properties: { code: { type: "string", description: 'ICF-Code ohne Beurteilungsmerkmal, z. B. "d450", "b1440", "e310"' } },
  required: ["code"],
};

const readOnly = { readOnlyHint: true, openWorldHint: false };

const TOOLS = [
  {
    name: "icf_search",
    title: "ICF durchsuchen",
    description:
      "Volltextsuche in Titeln, Beschreibungen und Einschlüssen der ICF-Kategorien. Mehrere Wörter werden UND-verknüpft; Umlaute und Groß-/Kleinschreibung sind egal. Auch Code-Präfixe (z. B. \"d45\") funktionieren.",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: 'Suchbegriff(e), z. B. "Treppen steigen" oder "Gedächtnis"' },
        component: { type: "string", enum: ["b", "s", "d", "e"], description: "Optional: auf eine Komponente einschränken" },
        limit: { type: "integer", minimum: 1, maximum: 100, default: 20 },
      },
      required: ["query"],
    },
    annotations: readOnly,
    run: icf.search,
  },
  {
    name: "icf_get_code",
    title: "ICF-Code abrufen",
    description:
      "Vollständige Angaben zu einem ICF-Code: Titel, Beschreibung, Definitionen, Ein- und Ausschlüsse (mit aufgelösten Codes), Pfad in der Hierarchie und Unterkategorien.",
    inputSchema: codeParam,
    annotations: readOnly,
    run: icf.getCode,
  },
  {
    name: "icf_list_chapters",
    title: "ICF-Kapitel auflisten",
    description: "Listet die vier ICF-Komponenten (b, s, d, e) mit ihren Kapiteln, oder nur die Kapitel einer Komponente.",
    inputSchema: {
      type: "object",
      properties: { component: { type: "string", enum: ["b", "s", "d", "e"], description: "Optional: nur diese Komponente" } },
    },
    annotations: readOnly,
    run: icf.listChapters,
  },
  {
    name: "icf_get_related",
    title: "Verwandte ICF-Codes",
    description: "Übergeordnete Kategorie, Geschwister, Unterkategorien und über Ausschlüsse verknüpfte Codes zu einem ICF-Code.",
    inputSchema: codeParam,
    annotations: readOnly,
    run: icf.getRelated,
  },
  {
    name: "icf_get_qualifiers",
    title: "Beurteilungsmerkmale",
    description:
      "Erklärt die Beurteilungsmerkmale (Qualifier) für einen ICF-Code: Notation, Bedeutung der Stellen und Werteskala (0–4, 8, 9 bzw. Art/Lokalisation bei s-Codes).",
    inputSchema: codeParam,
    annotations: readOnly,
    run: icf.getQualifiers,
  },
  {
    name: "icf_interpret_coding",
    title: "ICF-Kodierung prüfen",
    description:
      "Prüft und übersetzt eine vollständige ICF-Kodierung mit Beurteilungsmerkmalen in Klartext, z. B. \"d450.23\", \"b1440.2\", \"s7500.213\", \"e310+3\" oder \"e150.2\". Meldet ungültige Codes und Werte.",
    inputSchema: {
      type: "object",
      properties: { coding: { type: "string", description: 'Kodierung, z. B. "d450.23" oder "e310+3"' } },
      required: ["coding"],
    },
    annotations: readOnly,
    run: icf.interpretCoding,
  },
];

const toolsByName = Object.fromEntries(TOOLS.map((t) => [t.name, t]));

function callTool({ name, arguments: args = {} }) {
  const tool = toolsByName[name];
  if (!tool) return { error: { code: -32602, message: `Unbekanntes Tool: ${name}` } };
  try {
    const data = tool.run(args);
    return {
      result: {
        content: [{ type: "text", text: JSON.stringify(data, null, 2) }],
        structuredContent: Array.isArray(data) ? { items: data } : data,
      },
    };
  } catch (err) {
    if (!(err instanceof icf.IcfError)) throw err;
    return { result: { content: [{ type: "text", text: err.message }], isError: true } };
  }
}

/** Verarbeitet eine JSON-RPC-Nachricht. Gibt die Antwort zurück oder null bei Notifications. */
export function handleMessage(msg) {
  const { id, method, params = {} } = msg ?? {};
  const isRequest = id !== undefined && id !== null;
  let outcome;

  switch (method) {
    case "initialize": {
      const requested = params.protocolVersion;
      outcome = {
        result: {
          protocolVersion: PROTOCOL_VERSIONS.includes(requested) ? requested : PROTOCOL_VERSIONS[0],
          capabilities: { tools: { listChanged: false } },
          serverInfo: SERVER_INFO,
          instructions: INSTRUCTIONS,
        },
      };
      break;
    }
    case "ping":
      outcome = { result: {} };
      break;
    case "tools/list":
      outcome = { result: { tools: TOOLS.map(({ run, ...def }) => def) } };
      break;
    case "tools/call":
      outcome = callTool(params);
      break;
    default:
      if (!isRequest) return null; // z. B. notifications/initialized
      outcome = { error: { code: -32601, message: `Methode nicht unterstützt: ${method}` } };
  }
  return isRequest ? { jsonrpc: "2.0", id, ...outcome } : null;
}
