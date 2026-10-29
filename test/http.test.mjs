import { test } from "node:test";
import assert from "node:assert/strict";
import { handleHttp } from "../src/http.mjs";
import netlifyFunction, { config } from "../netlify/functions/mcp.mjs";

const post = (body) =>
  new Request("https://example.org/mcp", {
    method: "POST",
    headers: { "content-type": "application/json", accept: "application/json, text/event-stream" },
    body: typeof body === "string" ? body : JSON.stringify(body),
  });

test("initialize und tools/call liefern JSON", async () => {
  const init = await handleHttp(post({ jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2025-06-18" } }));
  assert.equal(init.status, 200);
  assert.match(init.headers.get("content-type"), /application\/json/);
  assert.equal((await init.json()).result.serverInfo.name, "icf");

  const call = await handleHttp(
    post({ jsonrpc: "2.0", id: 2, method: "tools/call", params: { name: "icd_check_code", arguments: { code: "F32.1 G" } } })
  );
  const { result } = await call.json();
  assert.equal(JSON.parse(result.content[0].text).title, "Mittelgradige depressive Episode");
});

test("Notifications ergeben 202 ohne Inhalt, Batches ein Array", async () => {
  const note = await handleHttp(post({ jsonrpc: "2.0", method: "notifications/initialized" }));
  assert.equal(note.status, 202);
  assert.equal(await note.text(), "");

  const batch = await handleHttp(
    post([
      { jsonrpc: "2.0", method: "notifications/initialized" },
      { jsonrpc: "2.0", id: 3, method: "ping" },
    ])
  );
  assert.deepEqual(await batch.json(), [{ jsonrpc: "2.0", id: 3, result: {} }]);
});

test("Fehlerfälle: ungültiges JSON und andere Methoden als POST", async () => {
  const bad = await handleHttp(post("kein json"));
  assert.equal(bad.status, 400);
  assert.equal((await bad.json()).error.code, -32700);

  const get = await handleHttp(new Request("https://example.org/mcp"));
  assert.equal(get.status, 405);
  assert.equal(get.headers.get("allow"), "POST");
});

test("Netlify-Function ist unter /mcp mit Ratenbegrenzung konfiguriert", async () => {
  assert.equal(config.path, "/mcp");
  assert.ok(config.rateLimit.windowLimit > 0);
  const res = await netlifyFunction(post({ jsonrpc: "2.0", id: 4, method: "tools/list" }));
  assert.equal((await res.json()).result.tools.length, 10);
});
