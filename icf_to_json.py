#!/usr/bin/env python3
"""icf_to_json.py

Vollständiger Export des ICF-ClaML-XML in eine hierarchische
JSON-Struktur **plus** eine Reihe von Komfort-Funktionen für spätere
API- und Analyse-Zwecke.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import textwrap
import xml.etree.ElementTree as ET
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List, Sequence

########################
# Grundlegende Parser  #
########################

XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
RUBRIC_KINDS = [
    "preferred",
    "definition",
    "coding-hint",
    "inclusion",
    "exclusion",
    "text",
]

def build_code_map(root: ET.Element) -> Dict[str, ET.Element]:
    return {cls.attrib["code"]: cls for cls in root.findall("Class")}

def get_children_codes(cls_elem: ET.Element) -> List[str]:
    return [sub.attrib["code"] for sub in cls_elem.findall("SubClass")]

def extract_rubrics(cls_elem: ET.Element, kind: str, lang: str = "de") -> List[str]:
    texts: List[str] = []
    for rubric in cls_elem.findall("Rubric"):
        if rubric.attrib.get("kind") != kind:
            continue
        for label in rubric.findall("Label"):
            label_lang = label.attrib.get(XML_LANG, lang)
            if label_lang == lang or XML_LANG not in label.attrib:
                t = (label.text or "").strip()
                if t:
                    texts.append(" ".join(t.split()))
    return texts

def class_to_dict(cls_elem: ET.Element, lang: str = "de") -> Dict:
    data: Dict[str, object] = {
        "code": cls_elem.attrib["code"],
        "kind": cls_elem.attrib.get("kind"),
        "children": get_children_codes(cls_elem),
    }
    for kind in RUBRIC_KINDS:
        texts = extract_rubrics(cls_elem, kind, lang)
        if not texts:
            continue
        if kind == "preferred":
            data["preferred"] = texts[0]
            if len(texts) > 1:
                data["preferred_full"] = texts
        else:
            data[f"{kind}s"] = texts
    return data

##########################################
# Export-Logik (rekursiv + Index)        #
##########################################

def _save_class_recursive(
    cls_elem: ET.Element,
    code_map: Dict[str, ET.Element],
    target_dir: Path,
    lang: str,
    index: Dict[str, str],
) -> None:
    cls_dir = target_dir / cls_elem.attrib["code"]
    cls_dir.mkdir(parents=True, exist_ok=True)
    data = class_to_dict(cls_elem, lang)
    json_path = cls_dir / f"{data['code']}.json"
    json_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    index[data["code"]] = str(json_path.relative_to(target_dir))
    for child_code in data["children"]:
        child_elem = code_map.get(child_code)
        if child_elem is None:
            print(f"Warnung: Unterklasse {child_code} nicht gefunden", file=sys.stderr)
            continue
        _save_class_recursive(child_elem, code_map, cls_dir, lang, index)

def export_icf(xml_path: Path, target_dir: Path, lang: str = "de") -> None:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    code_map = build_code_map(root)
    tops = [c for c in code_map.values() if c.attrib.get("kind") == "component"]
    index: Dict[str, str] = {}
    for comp in tops:
        _save_class_recursive(comp, code_map, target_dir, lang, index)
    (target_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

##########################################
# Komfort-Funktionen für den API-Einsatz  #
##########################################

def load_index(target_dir: Path) -> Dict[str, str]:
    return json.loads((target_dir / "index.json").read_text(encoding="utf-8"))

def load_class(code: str, index_path: Path | str) -> Dict:
    index = json.loads(Path(index_path).read_text(encoding="utf-8"))
    rel = index.get(code)
    if rel is None:
        raise KeyError(f"Code {code!r} nicht in Index")
    return json.loads((Path(index_path).parent / rel).read_text(encoding="utf-8"))

def search_text(
    query: str,
    index_path: Path | str,
    *,
    fields: Sequence[str] = ("preferred", "definitions", "coding-hints"),
    limit: int | None = 20,
) -> List[Dict]:
    q_lower = query.lower()
    results: List[Dict] = []
    index = json.loads(Path(index_path).read_text(encoding="utf-8"))
    for code, rel in index.items():
        p = Path(index_path).parent / rel
        if not p.is_file():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        for fld in fields:
            val = data.get(fld)
            if val and (
                (isinstance(val, str) and q_lower in val.lower())
                or (isinstance(val, Iterable) and any(q_lower in str(x).lower() for x in val))
            ):
                results.append(data)
                break
        if limit and len(results) >= limit:
            break
    return results

def list_children(
    code: str,
    index_path: Path | str,
    *,
    depth: int = 1,
) -> List[str]:
    parent = load_class(code, index_path)
    children: List[str] = []
    def _collect(codes: List[str], d: int):
        if d <= 0:
            return
        for c in codes:
            children.append(c)
            sub = load_class(c, index_path)
            _collect(sub.get("children", []), d - 1)
    _collect(parent.get("children", []), depth)
    return children

def stats(target_dir: Path) -> Dict[str, object]:
    index = load_index(target_dir)
    total = len(index)
    depths: List[int] = []
    child_counts: List[int] = []
    missing: List[str] = []
    for code, rel in index.items():
        p = target_dir / rel
        if not p.is_file():
            print(f"⚠️ Warnung: {p} fehlt – Code {code} übersprungen", file=sys.stderr)
            missing.append(code)
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        depths.append(rel.count("/"))
        child_counts.append(len(data.get("children", [])))
    stats: Dict[str, object] = {
        "total_classes": total - len(missing),
        "max_depth": max(depths) if depths else 0,
        "avg_children": round(mean(child_counts), 2) if child_counts else 0,
    }
    if missing:
        print(f"⚠️ {len(missing)} Einträge konnten in stats nicht verarbeitet werden.", file=sys.stderr)
    return stats

##########################################
# Hilfsfunktionen  (Flat + Update)       #
##########################################

def create_flat_json(target_dir: Path, fname: str = "icf_flat.json") -> None:
    index = load_index(target_dir)
    flat: Dict[str, Dict] = {}
    missing: List[str] = []
    for code, rel in index.items():
        p = target_dir / rel
        if not p.is_file():
            print(f"⚠️ Warnung: {p} fehlt – Code {code} übersprungen", file=sys.stderr)
            missing.append(code)
            continue
        flat[code] = json.loads(p.read_text(encoding="utf-8"))
    (target_dir / fname).write_text(
        json.dumps(flat, ensure_ascii=False, separators=",:"), encoding="utf-8"
    )
    if missing:
        print(f"⚠️ {len(missing)} Einträge konnten nicht übernommen werden.", file=sys.stderr)

def update_cache(xml_path: Path, target_dir: Path, lang: str = "de") -> None:
    export_icf(xml_path, target_dir, lang)

def export_language(xml_path: Path, target_dir: Path, lang: str) -> None:
    export_icf(xml_path, target_dir, lang)

##########################################
# Kommandozeilen-Interface               #
##########################################

def _cli_stats(target_dir: Path):
    s = stats(target_dir)
    print("\n".join(f"{k}: {v}" for k, v in s.items()))

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ICF ClaML → hierarchische JSON-Export-Routine mit Zusatz-APIs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """
Beispiel:
  python3 icf_to_json.py icf.xml ./icf_json --clean --lang de --flatten --stats
"""
        )
    )
    parser.add_argument("xml_path",   type=Path, help="Pfad zur ClaML-XML")
    parser.add_argument("target_dir", type=Path, help="Zielordner")
    parser.add_argument("--lang",     default="de", action="store", help="ISO-Sprachcode (de, en …)")
    parser.add_argument("--flatten",  action="store_true", help="Erzeuge icf_flat.json")
    parser.add_argument("--stats",    action="store_true", help="Gib Basis-Statistiken aus")
    parser.add_argument("--clean",    action="store_true", help="Vorher Zielordner löschen")
    args = parser.parse_args()

    if args.clean and args.target_dir.exists():
        shutil.rmtree(args.target_dir)
    args.target_dir.mkdir(parents=True, exist_ok=True)

    export_icf(args.xml_path, args.target_dir, args.lang)
    if args.flatten:
        create_flat_json(args.target_dir)
    if args.stats:
        _cli_stats(args.target_dir)

if __name__ == "__main__":
    main()
