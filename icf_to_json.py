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

def export_icf(xml_path: Path, target_dir: Path, lang: str = "de") -> Dict[str, str]:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    code_map = build_code_map(root)
    tops = [c for c in code_map.values() if c.attrib.get("kind") == "component"]
    index: Dict[str, str] = {}
    for comp in tops:
        _save_class_recursive(comp, code_map, target_dir, lang, index)
    # Schreibe Datei, falls gewünscht
    (target_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    # Gib Index zurück
    return index

##########################################
# Komfort-Funktionen für den API-Einsatz  #
##########################################

def create_flat_json(target_dir: Path) -> None:
    """
    Erstellt eine flache JSON-Datei aus den hierarchischen JSON-Dateien.
    
    Args:
        target_dir: Verzeichnis, in dem die index.json und alle anderen JSON-Dateien liegen
    """
    # Index-Datei lesen
    index_path = target_dir / "index.json"
    if not index_path.exists():
        print(f"Fehler: Index-Datei {index_path} nicht gefunden", file=sys.stderr)
        return

    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)
    
    # Flat-Dictionary erstellen
    flat_dict: Dict[str, Dict] = {}
    missing_files = []
    
    # Hilfsfunktion zum Finden von Dateien mit dem gleichen Basisnamen in einer verschachtelten Struktur
    def find_file_by_code(base_dir: Path, code: str) -> Path:
        # Versuche, die Datei durch rekursive Suche zu finden
        for json_file in base_dir.glob(f"**/{code}.json"):
            return json_file
        # Wenn nicht gefunden, versuche alternativ, in dem angegebenen Verzeichnis zu suchen
        possible_dir = base_dir / code
        if possible_dir.exists() and possible_dir.is_dir():
            possible_file = possible_dir / f"{code}.json"
            if possible_file.exists():
                return possible_file
        # Nichts gefunden
        return None
    
    # Alle JSON-Dateien aus dem Index laden
    for code, rel_path in index.items():
        # Versuche zuerst den direkten Pfad
        json_path = target_dir / rel_path
        found = False
        
        if json_path.exists():
            # Direkte Pfadauflösung erfolgreich
            found = True
        else:
            # Versuche, die Datei durch den Code zu finden
            alternative_path = find_file_by_code(target_dir, code)
            if alternative_path:
                json_path = alternative_path
                print(f"Info: JSON-Datei für Code {code} gefunden unter {json_path}", file=sys.stderr)
                found = True
        
        if not found:
            missing_files.append((code, str(json_path)))
            continue
            
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            # Code in das flache Dictionary einfügen
            flat_dict[code] = data
        except Exception as e:
            print(f"Fehler beim Lesen von {json_path}: {e}", file=sys.stderr)
    
    # Ausgabe von Warnungen zu fehlenden Dateien
    if missing_files:
        print(f"Warnung: {len(missing_files)} JSON-Dateien wurden nicht gefunden:", file=sys.stderr)
        for code, path in missing_files[:10]:  # Begrenze die Ausgabe auf 10 Einträge
            print(f"  - Code {code}: {path}", file=sys.stderr)
        if len(missing_files) > 10:
            print(f"  ... und {len(missing_files) - 10} weitere.", file=sys.stderr)
    
    # Flache JSON-Datei schreiben
    flat_json_path = target_dir / "icf_flat.json"
    flat_json_path.write_text(
        json.dumps(flat_dict, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"Flache JSON-Datei erstellt: {flat_json_path} mit {len(flat_dict)} ICF-Codes")

def _cli_stats(target_dir: Path) -> None:
    """
    Gibt Basis-Statistiken über die ICF-Daten aus.
    
    Args:
        target_dir: Verzeichnis, in dem die index.json liegt
    """
    # Diese Funktion sollte später implementiert werden
    print("Statistiken werden noch nicht unterstützt.")

##########################################
# Kommandozeilen-Interface               #
##########################################

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

    # Exportiere und erhalte Index
    index = export_icf(args.xml_path, args.target_dir, args.lang)

    # Optional: Flatten und Stats
    if args.flatten:
        create_flat_json(args.target_dir)
    if args.stats:
        _cli_stats(args.target_dir)

    # Ausgabe des Index auf stdout
    print(json.dumps(index, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

