#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# build_data.sh
# Erzeugt data/ aus den ClaML-Quelldateien in source/:
#   icf_flat.json, qualifiers.json  (ICF)
#   icd10gm.json                    (ICD-10-GM)
# Aufruf aus beliebigem Ordner: scripts/build_data.sh [ZIEL] [PYTHON]
# ---------------------------------------------------------------------------

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

OUT_DIR="${1:-$ROOT_DIR/data}"
PY_CMD="${2:-python3}"
ICF_XML="$ROOT_DIR/source/icf2005syst_claml_20120619.xml"
ICD_XML="$(ls "$ROOT_DIR"/source/icd10gm*syst_claml_*.xml | sort | tail -1)"

if ! command -v "$PY_CMD" &>/dev/null; then
  echo "❌ Python-Interpreter '$PY_CMD' nicht gefunden." >&2
  exit 1
fi
for f in "$ICF_XML" "$ICD_XML"; do
  if [[ ! -f "$f" ]]; then
    echo "❌ XML-Datei '$f' nicht gefunden." >&2
    exit 1
  fi
done

printf "ICF: %s\nICD: %s\nZiel: %s\n\n" "$ICF_XML" "$ICD_XML" "$OUT_DIR"
"$PY_CMD" "$SCRIPT_DIR/icf_to_json.py" "$ICF_XML" "$OUT_DIR" --lang de
"$PY_CMD" "$SCRIPT_DIR/icd_to_json.py" "$ICD_XML" "$OUT_DIR"
