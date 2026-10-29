#!/usr/bin/env python3
"""icf_to_json.py

Export des ICF-ClaML-XML nach JSON für den MCP-Server:
  icf_flat.json   – alle Kategorien, nach Code, in Hierarchie-Reihenfolge
  qualifiers.json – Beurteilungsmerkmale je Komponente
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List

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
# Export-Logik                           #
##########################################

def _collect_recursive(
    cls_elem: ET.Element,
    code_map: Dict[str, ET.Element],
    lang: str,
    flat: Dict[str, Dict],
) -> None:
    data = class_to_dict(cls_elem, lang)
    flat[data["code"]] = data
    for child_code in data["children"]:
        child_elem = code_map.get(child_code)
        if child_elem is None:
            print(f"Warnung: Unterklasse {child_code} nicht gefunden", file=sys.stderr)
            continue
        _collect_recursive(child_elem, code_map, lang, flat)

def export_icf(xml_path: Path, target_dir: Path, lang: str = "de") -> Dict[str, Dict]:
    root = ET.parse(xml_path).getroot()
    code_map = build_code_map(root)
    flat: Dict[str, Dict] = {}
    for comp in (c for c in code_map.values() if c.attrib.get("kind") == "component"):
        _collect_recursive(comp, code_map, lang, flat)
    (target_dir / "icf_flat.json").write_text(
        json.dumps(flat, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    export_qualifiers(root, target_dir, lang)
    return flat

def _label_text(label: ET.Element) -> str:
    # Modifier-Rubriken enthalten verschachtelte <Para>-Elemente
    return " ".join(" ".join(label.itertext()).split())

def export_qualifiers(root: ET.Element, target_dir: Path, lang: str = "de") -> None:
    """
    Exportiert die ICF-Beurteilungsmerkmale (ClaML-Modifier) nach qualifiers.json.

    Struktur: {"modifiers": {code: {...}}, "components": {"b": [modifier-codes], ...}}
    """
    def rubrics(elem: ET.Element, kind: str) -> List[str]:
        return [
            _label_text(label)
            for rubric in elem.findall("Rubric") if rubric.attrib.get("kind") == kind
            for label in rubric.findall("Label")
            if label.attrib.get(XML_LANG, lang) == lang and _label_text(label)
        ]

    modifiers: Dict[str, Dict] = {}
    for mod in root.findall("Modifier"):
        preferred = rubrics(mod, "preferred")
        modifiers[mod.attrib["code"]] = {
            "code": mod.attrib["code"],
            "preferred": preferred[0] if preferred else mod.attrib["code"],
            "definitions": rubrics(mod, "definition"),
            "values": [],
        }
    for mc in root.findall("ModifierClass"):
        mod = modifiers.get(mc.attrib["modifier"])
        if mod is None:
            continue
        preferred = rubrics(mc, "preferred")
        mod["values"].append({
            # Codes liegen teils als "xxx:0", teils als "xxx:xxx.0" vor
            "value": mc.attrib["code"].split(":", 1)[-1].removeprefix("xxx."),
            "preferred": preferred[0] if preferred else "",
        })

    components = {
        cls.attrib["code"]: [mb.attrib["code"] for mb in cls.findall("ModifiedBy")]
        for cls in root.findall("Class") if cls.findall("ModifiedBy")
    }
    (target_dir / "qualifiers.json").write_text(
        json.dumps({"modifiers": modifiers, "components": components}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

##########################################
# Kommandozeilen-Interface               #
##########################################

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ICF ClaML → icf_flat.json und qualifiers.json",
        epilog="Beispiel: python3 icf_to_json.py source/icf.xml ./data --lang de",
    )
    parser.add_argument("xml_path",   type=Path, help="Pfad zur ClaML-XML")
    parser.add_argument("target_dir", type=Path, help="Zielordner")
    parser.add_argument("--lang",     default="de", action="store", help="ISO-Sprachcode (de, en …)")
    args = parser.parse_args()

    args.target_dir.mkdir(parents=True, exist_ok=True)
    flat = export_icf(args.xml_path, args.target_dir, args.lang)
    print(f"{len(flat)} ICF-Codes nach {args.target_dir} exportiert")

if __name__ == "__main__":
    main()
