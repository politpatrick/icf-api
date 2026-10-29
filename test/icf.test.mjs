import { test } from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { handleMessage } from "../src/protocol.mjs";

let nextId = 1;
function call(name, args) {
  const reply = handleMessage({ jsonrpc: "2.0", id: nextId++, method: "tools/call", params: { name, arguments: args } });
  return reply.result.isError ? { error: reply.result.content[0].text } : JSON.parse(reply.result.content[0].text);
}

test("initialize handelt die Protokollversion aus", () => {
  const known = handleMessage({ jsonrpc: "2.0", id: 1, method: "initialize", params: { protocolVersion: "2025-03-26" } });
  assert.equal(known.result.protocolVersion, "2025-03-26");
  assert.equal(known.result.serverInfo.name, "icf");
  const unknown = handleMessage({ jsonrpc: "2.0", id: 2, method: "initialize", params: { protocolVersion: "1999-01-01" } });
  assert.equal(unknown.result.protocolVersion, "2025-06-18");
});

test("Notifications bekommen keine Antwort, unbekannte Methoden einen Fehler", () => {
  assert.equal(handleMessage({ jsonrpc: "2.0", method: "notifications/initialized" }), null);
  assert.equal(handleMessage({ jsonrpc: "2.0", id: 3, method: "foo/bar" }).error.code, -32601);
});

test("tools/list liefert alle Tools ohne interne Felder", () => {
  const { tools } = handleMessage({ jsonrpc: "2.0", id: 4, method: "tools/list" }).result;
  assert.deepEqual(tools.map((t) => t.name).sort(), [
    "icd_check_code", "icd_get_code", "icd_list_chapters", "icd_search",
    "icf_get_code", "icf_get_qualifiers", "icf_get_related", "icf_interpret_coding", "icf_list_chapters", "icf_search",
  ]);
  assert.ok(tools.every((t) => !("run" in t) && t.inputSchema));
});

test("icf_search findet Treffer unabhängig von Umlaut-Schreibweise", () => {
  const umlaut = call("icf_search", { query: "Gedächtnis Kurzzeit" });
  const ascii = call("icf_search", { query: "gedaechtnis kurzzeit" });
  assert.equal(umlaut.results[0].code, "b1440");
  assert.deepEqual(ascii.results, umlaut.results);
  assert.ok(call("icf_search", { query: "Treppe", component: "d" }).results.every((r) => r.code.startsWith("d")));
});

test("icf_get_code liefert Pfad, Kinder und aufgelöste Ausschlüsse", () => {
  const d450 = call("icf_get_code", { code: "D450" });
  assert.equal(d450.title, "Gehen");
  assert.deepEqual(d450.path.map((p) => p.code), ["d", "d4", "d450-d469"]);
  assert.ok(d450.children.some((c) => c.code === "d4500"));
  assert.equal(d450.exclusions[0].codes[0].code, "d420");
  assert.match(call("icf_get_code", { code: "x999" }).error, /nicht gefunden/);
});

test("icf_get_related liefert Eltern und Geschwister", () => {
  const related = call("icf_get_related", { code: "d4500" });
  assert.equal(related.parent.code, "d450");
  assert.ok(related.siblings.some((s) => s.code === "d4501"));
  assert.ok(!related.siblings.some((s) => s.code === "d4500"));
});

test("icf_list_chapters listet Komponenten und Kapitel", () => {
  const all = call("icf_list_chapters", {});
  assert.deepEqual(all.map((c) => c.code), ["b", "s", "d", "e"]);
  const d = call("icf_list_chapters", { component: "d" });
  assert.equal(d[0].chapters.length >= 9, true);
});

test("icf_get_qualifiers kennt die Skalen je Komponente", () => {
  assert.equal(call("icf_get_qualifiers", { code: "s750" }).qualifiers.length, 3);
  assert.equal(call("icf_get_qualifiers", { code: "e310" }).qualifiers.length, 2);
  assert.match(call("icf_get_qualifiers", { code: "d450" }).qualifiers[0].values["2"], /mäßig/);
});

test("icf_interpret_coding übersetzt gültige Kodierungen", () => {
  const d = call("icf_interpret_coding", { coding: "d450.23" });
  assert.deepEqual(d.qualifiers.map((q) => q.value), ["2", "3"]);
  assert.match(d.qualifiers[0].position, /Leistung/);
  assert.deepEqual(d.warnings, []);

  const e = call("icf_interpret_coding", { coding: "e310+3" });
  assert.match(e.qualifiers[0].meaning, /Förderfaktor erheblich/);

  const s = call("icf_interpret_coding", { coding: "s7500.213" });
  assert.match(s.qualifiers[0].meaning, /mäßig/);
  assert.deepEqual(s.qualifiers.slice(1).map((q) => q.meaning), ["nicht vorhanden", "beidseitig"]);
});

test("icf_interpret_coding meldet Fehler und Warnungen", () => {
  assert.ok(call("icf_interpret_coding", { coding: "b1440" }).warnings.length);
  assert.ok(call("icf_interpret_coding", { coding: "b1440.7" }).warnings.some((w) => w.includes("nicht definiert")));
  assert.ok(call("icf_interpret_coding", { coding: "d450+2" }).warnings.some((w) => w.includes("Förderfaktoren")));
  assert.match(call("icf_interpret_coding", { coding: "quatsch" }).error, /keine gültige ICF-Kodierung/);
});

test("stdio-Server beantwortet zeilenweise JSON-RPC", async () => {
  const server = spawn(process.execPath, [fileURLToPath(new URL("../src/server.mjs", import.meta.url))]);
  const lines = [];
  server.stdout.setEncoding("utf-8");
  const done = new Promise((resolve) => {
    let buffer = "";
    server.stdout.on("data", (chunk) => {
      buffer += chunk;
      lines.push(...buffer.split("\n").slice(0, -1));
      buffer = buffer.slice(buffer.lastIndexOf("\n") + 1);
      if (lines.length >= 3) resolve();
    });
  });
  server.stdin.write('{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}\n');
  server.stdin.write('{"jsonrpc":"2.0","method":"notifications/initialized"}\n');
  server.stdin.write("kein json\n");
  server.stdin.write('{"jsonrpc":"2.0","id":2,"method":"ping"}\n');
  await done;
  server.kill();
  const [init, parseError, ping] = lines.map((l) => JSON.parse(l));
  assert.equal(init.result.serverInfo.name, "icf");
  assert.equal(parseError.error.code, -32700);
  assert.deepEqual(ping, { jsonrpc: "2.0", id: 2, result: {} });
});
