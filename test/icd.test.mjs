import { test } from "node:test";
import assert from "node:assert/strict";
import { handleMessage } from "../src/protocol.mjs";
import { normalizeIcdCode } from "../src/icd.mjs";

let nextId = 1;
function call(name, args) {
  const reply = handleMessage({ jsonrpc: "2.0", id: nextId++, method: "tools/call", params: { name, arguments: args } });
  return reply.result.isError ? { error: reply.result.content[0].text } : JSON.parse(reply.result.content[0].text);
}

test("normalizeIcdCode versteht gängige Schreibweisen", () => {
  assert.equal(normalizeIcdCode("f32.1"), "F32.1");
  assert.equal(normalizeIcdCode("F321"), "F32.1");
  assert.equal(normalizeIcdCode("E1190"), "E11.90");
  assert.equal(normalizeIcdCode("M07.0-*"), "M07.0");
  assert.equal(normalizeIcdCode("G30.0†"), "G30.0");
  assert.equal(normalizeIcdCode("F33.-"), "F33");
});

test("kombinierte Kodes werden aus den Subklassifikationen gebildet", () => {
  const e1190 = call("icd_get_code", { code: "E11.90" });
  assert.equal(e1190.title, "Diabetes mellitus, Typ 2: Ohne Komplikationen: Nicht als entgleist bezeichnet");
  assert.equal(e1190.terminal, true);
  assert.match(e1190.para301, /^P/);
  assert.deepEqual(e1190.path.map((p) => p.code), ["IV", "E10-E14", "E11", "E11.9"]);

  // excludeOnPrecedingModifier: E11.0 (mit Koma) gibt es nur als entgleist
  assert.deepEqual(call("icd_get_code", { code: "E11.0" }).children.map((c) => c.code), ["E11.01"]);
  assert.match(call("icd_get_code", { code: "E11.00" }).error, /nicht gefunden/);

  // ValidModifierClass: M07.0 erlaubt nur bestimmte fünfte Stellen
  assert.match(call("icd_get_code", { code: "M07.01" }).error, /nicht gefunden/);
  assert.equal(call("icd_get_code", { code: "M07.04" }).code, "M07.04*");
});

test("Kodierregeln werden nach BfArM-Liesmich vererbt", () => {
  const e119 = call("icd_get_code", { code: "E11.9" });
  assert.equal(e119.terminal, false);
  assert.match(e119.para295, /^P/); // nicht endständiger kombinierter Viersteller: ambulant zulässig
  assert.match(e119.para301, /^V/); // stationär nicht
  assert.match(call("icd_get_code", { code: "M07.04" }).para295, /^O/); // Stern-Kode
  assert.match(call("icd_get_code", { code: "F32" }).para301, /^V/);
});

test("icd_get_code liefert Ausschlüsse mit aufgelösten Verweisen", () => {
  const f32 = call("icd_get_code", { code: "F32" });
  const rezidivierend = f32.exclusions.find((e) => e.text.startsWith("rezidivierende"));
  assert.equal(rezidivierend.codes[0].code, "F33");
  assert.equal(f32.children.length, 6);
  assert.equal(call("icd_get_code", { code: "F30-F39" }).kind, "block");
  assert.equal(call("icd_get_code", { code: "G30.0" }).code, "G30.0†");
});

test("icd_search findet Diagnosen, auch kombinierte", () => {
  const dep = call("icd_search", { query: "mittelgradige depressive Episode" });
  assert.ok(dep.results.some((r) => r.code === "F32.1"));
  const fuss = call("icd_search", { query: "diabetes typ 2 fusssyndrom", codable_only: true });
  assert.ok(fuss.results.every((r) => r.terminal && r.code.startsWith("E11")));
  assert.ok(fuss.results.some((r) => r.code === "E11.74"));
  assert.ok(call("icd_search", { query: "depression", chapter: "V" }).results.every((r) => r.code.startsWith("F")));
  assert.equal(call("icd_search", { query: "F32.1" }).results[0].code, "F32.1");
});

test("icd_check_code prüft Kodierbarkeit und Zusatzkennzeichen", () => {
  const ok = call("icd_check_code", { code: "M17.1 R G" });
  assert.equal(ok.valid, true);
  assert.match(ok.certainty, /gesichert/);
  assert.match(ok.side, /rechts/);
  assert.match(call("icd_check_code", { code: "F32.1V" }).certainty, /Verdacht/);

  const unspecific = call("icd_check_code", { code: "F32" });
  assert.equal(unspecific.valid, false);
  assert.match(unspecific.warnings[0], /F32\.0, F32\.1/);

  assert.ok(call("icd_check_code", { code: "M07.04*" }).warnings.some((w) => w.includes("Kreuz-Kode")));
  assert.equal(call("icd_check_code", { code: "V" }).valid, false);
});

test("icd_list_chapters listet 22 Kapitel mit Bereichen", () => {
  const all = call("icd_list_chapters", {});
  assert.equal(all.chapters.length, 22);
  assert.equal(all.chapters.find((c) => c.code === "V").range, "F00-F99");
  assert.ok(call("icd_list_chapters", { chapter: "v" }).groups.some((g) => g.code === "F30-F39"));
  assert.match(call("icd_list_chapters", { chapter: "F32" }).error, /kein Kapitel/);
});
