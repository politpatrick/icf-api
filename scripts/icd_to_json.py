#!/usr/bin/env python3
"""icd_to_json.py

Export des ICD-10-GM-ClaML-XML (Systematisches Verzeichnis, BfArM) nach JSON für den MCP-Server:
  icd10gm.json – alle Klassen (Kapitel, Gruppen, Kategorien) einschließlich der über
                 Subklassifikationslisten (Modifier) kombinierten Kodes, nach Code.

Kombinierte Kodes werden nach den Hinweisen der BfArM-Liesmich gebildet:
Para295/Para301 und UsageKind werden vom nicht endständigen Kode geerbt, V wird bei
endständigen kombinierten Kodes (Para295 auch bei nicht endständigen Vierstellern) zu P,
P bei usage="aster" zu O bzw. bei usage="optional" zu Z.
"""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional

USAGE_MARK = {"aster": "*", "dagger": "†", "optional": "!"}
TEXT_RUBRICS = {
    "inclusion": "inclusions",
    "exclusion": "exclusions",
    "coding-hint": "coding_hints",
    "definition": "definitions",
    "note": "notes",
    "text": "notes",
    "introduction": "notes",
}
META_KEEP = ["Para295", "Para301", "SexCode", "SexReject", "AgeLow", "AgeHigh", "AgeReject", "Exotic", "Content", "Infectious"]

########################
# Texte und Referenzen #
########################

def _normalize_ref(text: str) -> str:
    # "F33.-" → F33, "M01.3-*" → M01.3, "U69.80!-U69.82" → U69.80-U69.82
    text = re.sub(r"[!*†]", "", text.strip())
    return re.sub(r"\.?-$", "", text)

def label_text(label: ET.Element, refs: Optional[List[str]] = None) -> str:
    parts: List[str] = []

    def walk(elem: ET.Element) -> None:
        if elem.tag == "Reference":
            ref_text = "".join(elem.itertext()).strip()
            if refs is not None:
                refs.append(_normalize_ref(elem.attrib.get("code") or ref_text))
            parts.append(f" ({ref_text})" if elem.attrib.get("class") == "in brackets" else f" {ref_text}")
        else:
            if elem.text:
                parts.append(elem.text)
            for child in elem:
                walk(child)
                if child.tag in ("Fragment", "Para", "ListItem", "Row"):
                    parts.append(" ")
        if elem is not label and elem.tail:
            parts.append(elem.tail)

    walk(label)
    return " ".join("".join(parts).split())

def collect_rubrics(elem: ET.Element, data: Dict) -> None:
    for rubric in elem.findall("Rubric"):
        kind = rubric.attrib.get("kind")
        for label in rubric.findall("Label"):
            if kind == "preferred":
                data["title"] = label_text(label)
            elif kind == "preferredLong":
                data["title_long"] = label_text(label)
            elif kind in TEXT_RUBRICS:
                refs: List[str] = []
                text = label_text(label, refs)
                if not text:
                    continue
                key = TEXT_RUBRICS[kind]
                entry = {"text": text, "refs": refs} if kind in ("inclusion", "exclusion") and refs else text
                data.setdefault(key, []).append(entry)

def metas(elem: ET.Element) -> Dict[str, str]:
    return {m.attrib["name"]: m.attrib["value"] for m in elem.findall("Meta") if m.attrib["name"] in META_KEEP}

##########################################
# Kombinierte Kodes (Modifier)           #
##########################################

def _para(value: str, usage: Optional[str], promote: bool) -> str:
    if promote and value == "V":
        value = "P"
    if value == "P" and usage == "aster":
        return "O"
    if value == "P" and usage == "optional":
        return "Z"
    return value

def expand_modifiers(
    base: Dict,
    modified_by: List[ET.Element],
    modifiers: Dict[str, Dict],
    out: Dict[str, Dict],
) -> None:
    """Bildet rekursiv die kombinierten Kodes eines Kodes mit Subklassifikationslisten."""

    def combine(parent: Dict, level: int, chosen: Dict[str, str]) -> None:
        mb = modified_by[level]
        mod = modifiers[mb.attrib["code"]]
        valid = None if mb.attrib.get("all", "true") == "true" else {v.attrib["code"] for v in mb.findall("ValidModifierClass")}
        terminal = level == len(modified_by) - 1
        for mc in mod["classes"]:
            if valid is not None and mc["code"] not in valid:
                continue
            if any(chosen.get(mod_code) == value for mod_code, value in mc.get("exclude_on_preceding", [])):
                continue
            code = parent["code"] + mc["code"]
            usage = base.get("usage")
            meta = {**parent.get("meta", {}), **mc.get("meta", {})}
            meta["Para295"] = _para(parent["meta"]["Para295"], usage, terminal or len(code) == 5)
            meta["Para301"] = _para(parent["meta"]["Para301"], usage, terminal)
            entry: Dict = {
                "code": code,
                "kind": "category",
                "parent": parent["code"],
                "title": mc["title"],
                "combined": True,
                "children": [],
            }
            if usage:
                entry["usage"] = usage
            for key in ("inclusions", "exclusions", "definitions", "notes", "coding_hints"):
                if mc.get(key):
                    entry[key] = mc[key]
            entry["meta"] = meta
            parent["children"].append(code)
            out[code] = entry
            if not terminal:
                combine(entry, level + 1, {**chosen, mb.attrib["code"]: mc["code"]})

    combine(base, 0, {})

def parse_modifiers(root: ET.Element) -> Dict[str, Dict]:
    modifiers: Dict[str, Dict] = {}
    for mod in root.findall("Modifier"):
        data: Dict = {"code": mod.attrib["code"], "order": [s.attrib["code"] for s in mod.findall("SubClass")], "classes": []}
        collect_rubrics(mod, data)
        modifiers[mod.attrib["code"]] = data
    by_code: Dict[str, Dict[str, Dict]] = {code: {} for code in modifiers}
    for mc in root.findall("ModifierClass"):
        data = {"code": mc.attrib["code"]}
        collect_rubrics(mc, data)
        # Eine Modifier-Klasse kann mehrere Ausschlüsse haben, z. B. "S04E10_4 .0"
        excl = [m.attrib["value"].split(" ", 1) for m in mc.findall("Meta") if m.attrib["name"] == "excludeOnPrecedingModifier"]
        if excl:
            data["exclude_on_preceding"] = excl
        data["meta"] = metas(mc)
        by_code[mc.attrib["modifier"]][mc.attrib["code"]] = data
    for code, mod in modifiers.items():
        mod["classes"] = [by_code[code][c] for c in mod["order"] if c in by_code[code]]
    return modifiers

##########################################
# Export-Logik                           #
##########################################

def export_icd(xml_path: Path, target_dir: Path) -> Dict[str, Dict]:
    root = ET.parse(xml_path).getroot()
    modifiers = parse_modifiers(root)
    classes = {c.attrib["code"]: c for c in root.findall("Class")}
    flat: Dict[str, Dict] = {}

    def visit(code: str, parent: Optional[str]) -> None:
        cls = classes[code]
        data: Dict = {"code": code, "kind": cls.attrib.get("kind")}
        if parent:
            data["parent"] = parent
        if cls.attrib.get("usage"):
            data["usage"] = cls.attrib["usage"]
        collect_rubrics(cls, data)
        data["children"] = [s.attrib["code"] for s in cls.findall("SubClass")]
        meta = metas(cls)
        if meta:
            data["meta"] = meta
        flat[code] = data
        for child in data["children"]:
            visit(child, code)
        modified_by = cls.findall("ModifiedBy")
        if modified_by:
            mod_notes = [n for mb in modified_by for n in modifiers[mb.attrib["code"]].get("notes", [])]
            if mod_notes:
                data["modifier_notes"] = mod_notes
            expand_modifiers(data, modified_by, modifiers, flat)

    title = root.find("Title")
    order = next(m.attrib["value"] for m in root.findall("Meta") if m.attrib["name"] == "TopLevelSort").split()
    for chapter in order:
        visit(chapter, None)

    out = {
        "meta": {
            "classification": "ICD-10-GM",
            "version": title.attrib.get("version"),
            "date": title.attrib.get("date"),
            "title": title.text,
            "chapters": order,
        },
        "codes": flat,
    }
    (target_dir / "icd10gm.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return flat

##########################################
# Kommandozeilen-Interface               #
##########################################

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ICD-10-GM ClaML → icd10gm.json",
        epilog="Beispiel: python3 icd_to_json.py source/icd10gm2026syst_claml_20250912.xml ./data",
    )
    parser.add_argument("xml_path",   type=Path, help="Pfad zur ClaML-XML (Systematisches Verzeichnis)")
    parser.add_argument("target_dir", type=Path, help="Zielordner")
    args = parser.parse_args()

    args.target_dir.mkdir(parents=True, exist_ok=True)
    flat = export_icd(args.xml_path, args.target_dir)
    combined = sum(1 for e in flat.values() if e.get("combined"))
    print(f"{len(flat)} ICD-10-GM-Klassen ({combined} kombinierte Kodes) nach {args.target_dir} exportiert")

if __name__ == "__main__":
    main()
