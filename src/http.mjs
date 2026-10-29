// MCP über Streamable HTTP (zustandslos, nur JSON-Antworten) für Web-Request/Response-Umgebungen
// wie Netlify Functions. Nutzt denselben handleMessage() wie der stdio-Einstieg.

import { handleMessage } from "./protocol.mjs";

const JSON_HEADERS = { "content-type": "application/json" };

function rpcError(code, message, status) {
  return new Response(JSON.stringify({ jsonrpc: "2.0", id: null, error: { code, message } }), { status, headers: JSON_HEADERS });
}

/** Beantwortet einen MCP-Request. Nur POST; GET (SSE-Stream) und Sitzungen werden nicht angeboten. */
export async function handleHttp(req) {
  if (req.method !== "POST") {
    return new Response("Method not allowed – MCP-Endpunkt erwartet POST (Streamable HTTP).", {
      status: 405,
      headers: { allow: "POST" },
    });
  }

  let body;
  try {
    body = await req.json();
  } catch {
    return rpcError(-32700, "Parse error", 400);
  }

  const messages = Array.isArray(body) ? body : [body];
  const replies = [];
  for (const msg of messages) {
    try {
      if (msg?.method === "tools/call") console.info("tools/call", msg.params?.name);
      const reply = handleMessage(msg);
      if (reply) replies.push(reply);
    } catch (err) {
      console.error(err);
      if (msg?.id != null) replies.push({ jsonrpc: "2.0", id: msg.id, error: { code: -32603, message: "Interner Fehler" } });
    }
  }

  // Nur Notifications/Antworten vom Client: 202 ohne Inhalt
  if (!replies.length) return new Response(null, { status: 202 });
  return new Response(JSON.stringify(Array.isArray(body) ? replies : replies[0]), { status: 200, headers: JSON_HEADERS });
}
