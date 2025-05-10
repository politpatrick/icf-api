#!/usr/bin/env python3
"""icf_to_json.py

Extrahiert das offizielle ICF‑ClaML‑XML in ein hierarchisch aufgebautes
Verzeichnis aus JSON‑Dateien. Jeder Klassenknoten wird in einem eigenen
Unterordner (benannt nach seinem Code) gespeichert; zusätzlich entsteht
eine globale *index.json*, um schnellen Zugriff per Code zu erlauben.

Aufruf:
    python icf_to_json.py <icf_claml.xml> <zielordner> [--lang de]

Beispiel:
    python icf_to_json.py icf2005syst_claml_20120619.xml ./icf_json --lang de
"""

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional

########################
# Parsing‑Funktionen   #
########################

def build_code_map(root: ET.Element) -> Dict[str, ET.Element]:
    """Erstellt ein Mapping Code → Class‑Element für alle Klassen."""
    return {cls.attrib["code"]: cls for cls in root.findall("Class")}

def get_children_codes(cls_elem: ET.Element) -> List[str]:
    """Liest die Codes aller direkten Unterklassen."""
    return [sub.attrib["code"] for sub in cls_elem.findall("SubClass")]

def extract_rubric(cls_elem: ET.Element, kind: str, lang: str = "de") -> Optional[str]:
    """Gibt den Label‑Text einer bestimmten Rubric‑Art zurück (z.B. preferred, definition)."""
    for rubric in cls_elem.findall("Rubric"):
        if rubric.attrib.get("kind") == kind:
            label = rubric.find("Label")
            if label is not None and (label.attrib.get("{http://www.w3.org/XML/1998/namespace}lang", lang) == lang):
                return " ".join(label.text.split())
    return None

def class_to_dict(cls_elem: ET.Element, lang: str = "de") -> Dict:
    """Wandelt ein <Class>‑Element in ein Python‑Dict um."""
    data = {
        "code": cls_elem.attrib["code"],
        "kind": cls_elem.attrib.get("kind"),
        "preferred": extract_rubric(cls_elem, "preferred", lang),
        "definition": extract_rubric(cls_elem, "definition", lang),
        # Unterklassen‑Platzhalter, wird später befüllt
        "children": []
    }
    return data

###########################################
# Rekursive Export‑ und Speicherfunktionen #
###########################################

def save_class_recursive(
    cls_elem: ET.Element,
    code_map: Dict[str, ET.Element],
    target_dir: Path,
    lang: str,
    index: Dict[str, str],
) -> None:
    """Speichert die Klasse und ihre Unterklassen rekursiv."""
    # Verzeichnis für diese Klasse
    cls_dir = target_dir / cls_elem.attrib["code"]
    cls_dir.mkdir(parents=True, exist_ok=True)

    # Daten der Klasse
    data = class_to_dict(cls_elem, lang)
    child_codes = get_children_codes(cls_elem)
    data["children"] = child_codes

    # JSON­‑Datei schreiben
    json_path = cls_dir / f"{data['code']}.json"
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf‑8")

    # Index aktualisieren (relativer Pfad ab Zielwurzel)
    index[data["code"]] = str(json_path.relative_to(target_dir))

    # Rekursion
    for child_code in child_codes:
        child_elem = code_map.get(child_code)
        if child_elem is None:
            print(f"Warnung: Unterklasse {child_code} nicht gefunden", file=sys.stderr)
            continue
        save_class_recursive(child_elem, code_map, cls_dir, lang, index)

####################
# Öffentliche APIs #
####################

def export_icf(xml_path: Path, target_dir: Path, lang: str = "de") -> None:
    """Hauptfunktion: Parst die XML und erstellt die Ordnerstruktur."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    code_map = build_code_map(root)
    # Top‑Level‑Komponenten: kind="component"
    top_components = [c for c in code_map.values() if c.attrib.get("kind") == "component"]

    index: Dict[str, str] = {}
    for comp in top_components:
        save_class_recursive(comp, code_map, target_dir, lang, index)

    # Globales Index‑File
    (target_dir / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf‑8")

##############
# CLI‑Wrapper #
##############

def main() -> None:
    parser = argparse.ArgumentParser(description="ICF ClaML → hierarchische JSON‑Export‑Routine")
    parser.add_argument("xml_path", type=Path, help="Pfad zur ICF‑ClaML‑XML‑Datei")
    parser.add_argument("target_dir", type=Path, help="Zielverzeichnis für die JSON‑Struktur")
    parser.add_argument("--lang", default="de", help="Sprachcode (z.B. de, en)")
    args = parser.parse_args()

    args.target_dir.mkdir(parents=True, exist_ok=True)
    export_icf(args.xml_path, args.target_dir, args.lang)

if __name__ == "__main__":
    main()
