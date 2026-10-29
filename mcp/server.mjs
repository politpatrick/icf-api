#!/usr/bin/env node
// ICF-MCP-Server über stdio (für Claude Desktop / Claude Code).
// Nachrichten sind zeilenweise JSON-RPC; Logs gehen nach stderr.

import { createInterface } from "node:readline";
import { handleMessage } from "./protocol.mjs";

const send = (msg) => process.stdout.write(JSON.stringify(msg) + "\n");

createInterface({ input: process.stdin }).on("line", (line) => {
  if (!line.trim()) return;
  let msg;
  try {
    msg = JSON.parse(line);
  } catch {
    send({ jsonrpc: "2.0", id: null, error: { code: -32700, message: "Parse error" } });
    return;
  }
  for (const m of Array.isArray(msg) ? msg : [msg]) {
    try {
      const reply = handleMessage(m);
      if (reply) send(reply);
    } catch (err) {
      console.error(err);
      if (m?.id != null) send({ jsonrpc: "2.0", id: m.id, error: { code: -32603, message: String(err.message ?? err) } });
    }
  }
});
