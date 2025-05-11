#!/usr/bin/env python3
"""
icf_github_client.py

Client-Bibliothek, um direkt gegen das auf GitHub gehostete ICF-JSON-„Datenbank“
zu arbeiten. Bietet Funktionen zum Laden des Index, Einzelklassen-Abruf und
Wrapper für Suche, Strukturabfrage und Statistik.
"""

import requests
from statistics import mean
from typing import Dict, List, Any

# Basis-URL zum Repository (Raw-GitHub-Content)
BASE_URL = "https://raw.githubusercontent.com/politpatrick/icf-api/main/icf_json"


def fetch_index() -> Dict[str, str]:
    """Lädt index.json (Map von ICF-Code → relativer Pfad)."""
    url = f"{BASE_URL}/index.json"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()


def fetch_class(rel_path: str) -> Dict[str, Any]:
    """Lädt eine einzelne Klassen-JSON anhand ihres relativen Pfads."""
    url = f"{BASE_URL}/{rel_path}"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()


def search_text(
    query: str,
    fields: List[str] = ["preferred", "definitions", "coding-hints"],
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Durchsucht ausgewählte Felder nach dem Suchbegriff.

    :param query: Suchbegriff (kleingeschrieben wird intern verglichen)
    :param fields: Felder in der JSON-Datei, z.B. 'preferred' oder 'definitions'
    :param limit: Max. Anzahl der Treffer
    :return: Liste der Klassen-Dicts, die das Query enthalten
    """
    idx = fetch_index()
    results: List[Dict[str, Any]] = []
    q_lower = query.lower()

    for code, rel in idx.items():
        data = fetch_class(rel)
        for fld in fields:
            val = data.get(fld)
            if isinstance(val, str) and q_lower in val.lower():
                results.append(data)
                break
            if isinstance(val, list) and any(q_lower in str(x).lower() for x in val):
                results.append(data)
                break
        if len(results) >= limit:
            break
    return results


def list_children(
    code: str,
    depth: int = 1,
) -> List[str]:
    """
    Gibt alle Unterklassen-Codes bis zur angegebenen Tiefe zurück.

    :param code: Eltern-Code (z.B. 'b')
    :param depth: Rekursionstiefe (1 = nur direkte Kinder)
    :return: Liste von Codes
    """
    idx = fetch_index()
    rel = idx.get(code)
    if rel is None:
        raise KeyError(f"Code '{code}' nicht im Index gefunden")

    root = fetch_class(rel)
    children: List[str] = []

    def _collect(codes: List[str], d: int):
        if d <= 0:
            return
        for c in codes:
            children.append(c)
            sub = fetch_class(idx[c])
            _collect(sub.get("children", []), d - 1)

    _collect(root.get("children", []), depth)
    return children


def stats() -> Dict[str, Any]:
    """
    Ermittelt Basis-Kennzahlen:
      - total_classes: Gesamtzahl der Codes im Index
      - max_depth: Maximale Verzeichnistiefe (Baumtiefen-Proxy)
      - avg_children: Durchschnittliche Anzahl direkter Unterklassen
    """
    idx = fetch_index()
    depths: List[int] = []
    child_counts: List[int] = []

    for rel in idx.values():
        depths.append(rel.count("/"))
        data = fetch_class(rel)
        child_counts.append(len(data.get("children", [])))

    return {
        "total_classes": len(idx),
        "max_depth": max(depths) if depths else 0,
        "avg_children": round(mean(child_counts), 2) if child_counts else 0,
    }


# Beispiel-Nutzung
if __name__ == "__main__":
    print("Index: Loaded", len(fetch_index()), "entries")
    print("Stats:", stats())
    print("Children of 'b':", list_children('b', depth=1))
    print("Search for 'Mobilität':", [c['code'] for c in search_text('Mobilität')])
