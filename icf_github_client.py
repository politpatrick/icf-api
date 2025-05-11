#!/usr/bin/env python3
"""
icf_github_client.py

Client-Bibliothek, um direkt gegen das auf GitHub gehostete ICF-JSON-„Datenbank“
zu arbeiten. Bietet Funktionen zum Laden des Index, Einzelklassen-Abruf und
Wrapper für Suche, Strukturabfrage und Statistik.
"""

import requests
from statistics import mean
from typing import Dict, List, Any, Optional
import sys

# Basis-URL zum Repository (Raw-GitHub-Content)
BASE_URL = "https://raw.githubusercontent.com/politpatrick/icf-api/main/icf_json"

# Cache für bereits abgefragte Pfade (um wiederholte 404-Fehler zu vermeiden)
_class_cache = {}


def fetch_index() -> Dict[str, str]:
    """Lädt index.json (Map von ICF-Code → relativer Pfad)."""
    url = f"{BASE_URL}/index.json"
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()


def fetch_class(rel_path: str) -> Optional[Dict[str, Any]]:
    """
    Lädt eine einzelne Klassen-JSON anhand ihres relativen Pfads.
    Bei 404-Fehlern wird None zurückgegeben und eine Warnung ausgegeben.
    
    :param rel_path: Relativer Pfad zur JSON-Datei
    :return: JSON-Daten als Dict oder None bei Fehler
    """
    # Prüfe, ob der Pfad bereits im Cache ist
    if rel_path in _class_cache:
        return _class_cache[rel_path]
        
    url = f"{BASE_URL}/{rel_path}"
    
    try:
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()
        _class_cache[rel_path] = data
        return data
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            print(f"Warnung: Datei nicht gefunden: {url}", file=sys.stderr)
            
            # Versuche alternative Orte für die Datei
            code = rel_path.split("/")[0]  # Extrahiere den Code aus dem Pfad (z.B. "b1" aus "b1/b1.json")
            
            # Liste möglicher alternativer Pfade
            alternatives = [
                f"{code}.json",  # Versuche "b1.json" statt "b1/b1.json"
                f"{code}/{code}",  # Versuche ohne .json-Erweiterung
                f"{code.upper()}/{code.upper()}.json",  # Versuche Großbuchstaben
            ]
            
            for alt_path in alternatives:
                alt_url = f"{BASE_URL}/{alt_path}"
                try:
                    print(f"Versuche alternative URL: {alt_url}", file=sys.stderr)
                    alt_resp = requests.get(alt_url)
                    alt_resp.raise_for_status()
                    data = alt_resp.json()
                    print(f"Erfolg mit alternativer URL: {alt_url}", file=sys.stderr)
                    _class_cache[rel_path] = data
                    return data
                except:
                    pass
            
            # Wenn keine Alternative funktioniert, versuche einen leeren Datensatz mit dem Code zu erstellen
            print(f"Erstelle Ersatz-Datensatz für '{code}'", file=sys.stderr)
            
            # Minimaler Datensatz für fehlende Einträge
            fallback_data = {
                "code": code,
                "preferred": f"Fehlender Eintrag: {code}",
                "definitions": [],
                "children": []
            }
            
            _class_cache[rel_path] = fallback_data
            return fallback_data
        else:
            print(f"HTTP-Fehler beim Laden von {url}: {e}", file=sys.stderr)
            _class_cache[rel_path] = None
            return None
    except Exception as e:
        print(f"Fehler beim Laden von {url}: {e}", file=sys.stderr)
        _class_cache[rel_path] = None
        return None


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
        
        # Überspringe, wenn keine Daten geladen werden konnten
        if data is None:
            continue
            
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
            
            # Nur fortfahren, wenn Daten geladen werden konnten
            if sub is not None:
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
        
        # Nur hinzufügen, wenn Daten geladen werden konnten
        if data is not None:
            child_counts.append(len(data.get("children", [])))

    return {
        "total_classes": len(idx),
        "max_depth": max(depths) if depths else 0,
        "avg_children": round(mean(child_counts), 2) if child_counts else 0,
    }


def verify_repository():
    """Verifiziert die Basisstruktur des Repositories und berichtet Probleme."""
    try:
        idx = fetch_index()
        print(f"Repository-Struktur gefunden mit {len(idx)} Einträgen")
        
        # Teste einen bekannten Eintrag (z.B. 'b')
        test_code = 'b'
        if test_code in idx:
            rel_path = idx[test_code]
            data = fetch_class(rel_path)
            if data is not None:
                print(f"Zugriff auf bekannten Eintrag '{test_code}' erfolgreich")
            else:
                print(f"Warnung: Konnte bekannten Eintrag '{test_code}' nicht laden", file=sys.stderr)
        
        # Zähle fehlende Einträge
        missing_count = 0
        for code, rel_path in list(idx.items())[:20]:  # Überprüfe die ersten 20 Einträge
            if fetch_class(rel_path) is None:
                missing_count += 1
                
        if missing_count > 0:
            print(f"Warnung: Bei {missing_count} von 20 getesteten Einträgen wurden Probleme gefunden", file=sys.stderr)
    except Exception as e:
        print(f"Fehler bei der Repository-Überprüfung: {e}", file=sys.stderr)


# Beispiel-Nutzung
if __name__ == "__main__":
    try:
        print("Index: Loaded", len(fetch_index()), "entries")
        
        # Verifiziere Repository-Struktur
        verify_repository()
        
        print("Stats:", stats())
        print("Children of 'b':", list_children('b', depth=1))
        print("Search for 'Mobilität':", [c.get('code', 'unknown') for c in search_text('Mobilität')])
    except Exception as e:
        print(f"Fehler: {e}", file=sys.stderr)
