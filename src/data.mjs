// Findet die JSON-Daten unter data/ – lokal relativ zum Quellcode, in Netlify Functions
// (gebündelt, data/ per included_files) relativ zum Task-Root.

import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const CANDIDATES = [
  process.env.ICF_DATA_DIR,
  path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "data"),
  process.env.LAMBDA_TASK_ROOT && path.join(process.env.LAMBDA_TASK_ROOT, "data"),
  path.join(process.cwd(), "data"),
].filter(Boolean);

export function readData(file) {
  const dir = CANDIDATES.find((d) => existsSync(path.join(d, file)));
  if (!dir) throw new Error(`Datendatei ${file} nicht gefunden (gesucht in: ${CANDIDATES.join(", ")})`);
  return JSON.parse(readFileSync(path.join(dir, file), "utf-8"));
}
