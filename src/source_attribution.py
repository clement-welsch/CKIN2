"""Offline attribution for the optional ByMykel catalog; no remote asset loads."""

import html
import json
from pathlib import Path

REVISION = "b014e92bc37f4143ead2cb1af26aa85f2c3d6688"
SOURCE = "https://github.com/ByMykel/CSGO-API"
LICENSE_PATH = Path(__file__).resolve().parents[1] / "licenses/ByMykel-CSGO-API-MIT.txt"


def sources_page(root):
    escape = html.escape
    releases = []
    for path in sorted((Path(root) / "data/market/releases").glob("*.json")):
        release = json.loads(path.read_text(encoding="utf-8"))
        source, revision = release.get("source_url", ""), release.get("source_revision", "")
        reviewed = source.rstrip("/") == SOURCE and revision == REVISION
        releases.append("<tr>" + "".join("<td>" + escape(str(v)) + "</td>" for v in
                        (source, revision, release.get("collected_at", ""), "Référence vérifiée" if reviewed else "Revue de licence à vérifier")) + "</tr>")
    local = ("<div style='overflow:auto'><table><tr><th>Source déclarée</th><th>Révision</th><th>Import</th><th>Licence</th></tr>" +
             "".join(releases) + "</table></div>" if releases else "<p>Aucune release de catalogue importée localement.</p>")
    license_text = escape(LICENSE_PATH.read_text(encoding="utf-8"))
    return f"""<!doctype html><html lang="fr"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>CKIN2 · Sources et licences</title>
<style>body{{font:16px/1.7 system-ui;background:#101720;color:#e6edf5;margin:0}}main{{max-width:1000px;margin:auto;padding:28px}}a{{color:#f8b55c}}section{{padding:24px;background:#17202b;border-radius:14px;margin:20px 0}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}td,th{{padding:10px;text-align:left;border-bottom:1px solid #526079}}code{{overflow-wrap:anywhere}}</style>
<main><a href="/">← Portefeuille</a><h1>Sources et licences</h1>
<section><h2>ByMykel / CSGO-API</h2><p>Catalogue optionnel de métadonnées d'objets, créé par
<a href="{SOURCE}">ByMykel</a>. Licence MIT · Copyright (c) 2023 ByMykel.</p>
<p>Licence examinée le 04/11/2026 à la révision <code>{REVISION}</code>.
<a href="{SOURCE}/blob/{REVISION}/LICENSE">Source de la licence</a>.</p>
<p>Le catalogue reste un import local facultatif. Aucun catalogue ou visuel tiers n'est embarqué dans CKIN2.
Cette référence de licence ne signifie pas que tous les imports locaux ont été vérifiés.</p>
<p>Les droits sur les images, marques et contenus provenant de Valve sont distincts et restent à vérifier avant leur réutilisation.</p></section>
<section><h2>Provenance des imports locaux</h2>{local}</section>
<section><h2>Texte de licence conservé</h2><pre>{license_text}</pre></section></main></html>"""
