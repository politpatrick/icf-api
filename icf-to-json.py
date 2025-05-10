#!/usr/bin/env python3
"""icf_to_json.py

Extrahiert das offizielle ICF‑ClaML‑XML in eine hierarchische
Verzeichnisstruktur aus JSON‑Dateien.  Gegenüber der ersten Version
werden nun **alle im XML vorhandenen Rubrik‑Texte** (z. B. mehrere
Definitionen, Einschluss‑/Ausschluss‑Texte, Coding‑Hints) vollständig
übernommen.

Aufruf:
    python icf_to_json.py <icf_claml.xml> <zielordner> [--lang de]

Beispiel:
    python icf_to_json.py icf2005syst_claml_20120619.xml ./icf_json --lang de
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List

########################
# Parsing‑Funktionen   #
########################

def build_code_map(root: ET.Element) -> Dict[str, ET.Element]:
    """Erstellt ein Mapping *Code → Class‑Element* für alle Klassen."""
    return {cls.attrib["code"]: cls for cls in root.findall("Class")}


def get_children_codes(cls_elem: ET.Element) -> List[str]:
    """Gibt die Codes aller direkten Unterklassen zurück."""
    return [sub.attrib["code"] for sub in cls_elem.findall("SubClass")]


XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


def extract_rubrics(cls_elem: ET.Element, kind: str, lang: str = "de") -> List[str]:
    """Liefert **alle** Label‑Texte einer bestimmten Rubrik‑Art.

    * Erkennt Mehrfach‑Definitionen (Komponenten b, d, s, etc.).
    * Filtert nach Sprache; Label ohne *xml:lang* werden als *neutral* gezählt
      und mit ausgegeben, solange kein anderssprachliches Label in derselben
      Rubrik vorhanden ist.
    """
    texts: List[str] = []
    for rubric in cls_elem.findall("Rubric"):
        if rubric.attrib.get("kind") != kind:
            continue
        for label in rubric.findall("Label"):
            label_lang = label.attrib.get(XML_LANG, lang)
            if label_lang == lang or XML_LANG not in label.attrib:
                text = (label.text or "").strip()
                if text:
                    texts.append(" ".join(text.split()))  # Mehrzeilig → eine Zeile
    return texts


RUBRIC_KINDS = [
    "preferred",
    "definition",
    "coding-hint",
    "inclusion",
    "exclusion",
    "text",  # Sonstige erläuternde Texte
]


def class_to_dict(cls_elem: ET.Element, lang: str = "de") -> Dict:
    """Wandelt ein <Class>-Element in ein Python‑Dict um."""

    data: Dict[str, object] = {
        "code": cls_elem.attrib["code"],
        "kind": cls_elem.attrib.get("kind"),
        "children": get_children_codes(cls_elem),
    }

    # Alle Rubrik‑Arten systematisch auslesen
    for kind in RUBRIC_KINDS:
        texts = extract_rubrics(cls_elem, kind, lang)
        if not texts:
            continue
        # Für *preferred* nur das erste Label als String (Kürzel) ablegen,
        # zusätzlich eine Liste *preferred_full* für alle Fassungen.
        if kind == "preferred":
            data["preferred"] = texts[0]
            if len(texts) > 1:
                data["preferred_full"] = texts
        else:
            # Bei mehrfach vorkommenden Definitionen etc. immer Liste speichern
            data[f"{kind}s"] = texts  # → definitions, coding-hints, inclusions …
    return data

###########################################
# Rekursiver Export & Speicherung         #
###########################################

def save_class_recursive(
    cls_elem: ET.Element,
    code_map: Dict[str, ET.Element],
    target_dir: Path,
    lang: str,
    index: Dict[str, str],
) -> None:
    """Speichert die gegebene Klasse und alle Unterklassen rekursiv."""

    cls_dir = target_dir / cls_elem.attrib["code"]
    cls_dir.mkdir(parents=True, exist_ok=True)

    data = class_to_dict(cls_elem, lang)
    json_path = cls_dir / f"{data['code']}.json"
    json_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    index[data["code"]] = str(json_path.relative_to(target_dir))

    for child_code in data["children"]:
        child_elem = code_map.get(child_code)
        if child_elem is None:
            print(f"Warnung: Unterklasse {child_code} nicht gefunden", file=sys.stderr)
            continue
        save_class_recursive(child_elem, code_map, cls_dir, lang, index)


####################
# Öffentliche API  #
####################

def export_icf(xml_path: Path, target_dir: Path, lang: str = "de") -> None:
    """Parst das XML und erzeugt die komplette JSON‑Struktur."""

    tree = ET.parse(xml_path)
    root = tree.getroot()
    code_map = build_code_map(root)

    # Top‑Level‑Komponenten
    top_components = [
        c for c in code_map.values() if c.attrib.get("kind") == "component"
    ]

    index: Dict[str, str] = {}
    for comp in top_components:
        save_class_recursive(comp, code_map, target_dir, lang, index)

    # Globales Index‑File anlegen
    (target_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )

##############
# CLI‑Wrapper #
##############

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ICF ClaML → hierarchische JSON‑Export‑Routine (inkl. vollständiger Definitionen)"
    )
    parser.add_argument("xml_path", type=Path, help="Pfad zur ICF‑ClaML‑XML‑Datei")
    parser.add_argument("target_dir", type=Path, help="Zielverzeichnis für die JSON‑Struktur")
    parser.add_argument("--lang", default="de", help="ISO‑Sprachcode (de, en, …)")
    args = parser.parse_args()

    args.target_dir.mkdir(parents=True, exist_ok=True)
    export_icf(args.xml_path, args.target_dir, args.lang)


if __name__ == "__main__":
    main()