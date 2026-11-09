"""Compact, accessible summary over the shared portfolio valuation."""

from html import escape
from urllib.parse import urlencode

import pandas as pd

from dashboard_status import BASIS_LABELS, STALE_DAYS, coverage


def stamp(value):
    return str(value) if pd.notna(value) else 'Indisponible'


def money(value):
    return f'{value:,.2f} EUR' if pd.notna(value) else 'Indisponible'


def overview(data, params):
    status = coverage(data)
    def link(page, text):
        return '<a href="/?' + escape(urlencode({**params, 'page': page}), quote=True) + '">' + text + '</a>'
    def card(label, value):
        return '<article><small>' + label + '</small><strong>' + escape(str(value)) + '</strong></article>'
    mode = 'Consultation historique' if data['historical_mode'] else 'Patrimoine actuel connu'
    total_label = 'Total calculé · périmètre non vérifié' if status['unverified'] else 'Valeur totale'
    body = '<section aria-labelledby="portfolio-summary"><h2 id="portfolio-summary">' + mode + '</h2>'
    body += '<p class="coverage"><b>' + status['label'] + '</b></p><div class="cards">'
    body += card(total_label, money(status['total_value']))
    body += card('Sous-total connu · peut être partiel', money(status['known_value']))
    body += card('Objets distincts détenus ou de quantité inconnue', status['held_items']) + '</div>'
    body += '<p>Quantités renseignées : ' + str(status['known_quantities']) + '/' + str(status['held_items'])
    body += ' objets · prix disponibles : ' + str(status['priced_items']) + '/' + str(status['held_items']) + ' objets.</p>'
    body += '<p>Catégories non importées : ' + str(status['missing_categories']) + ' · prix anciens : ' + str(status['stale_items'])
    body += f' (plus de {STALE_DAYS} jours à la date d’analyse).</p>'
    provenance = data['provenance']
    body += '<h3>Dates et provenance</h3><dl><dt>Quantités</dt><dd>' + escape(BASIS_LABELS[provenance['basis']])
    body += ' · date : ' + escape(stamp(provenance.get('collected_at'))) + '</dd>'
    dates = status['rows'].price_date.dropna()
    body += '<dt>Prix utilisés</dt><dd>' + (escape(stamp(dates.min())) + ' → ' + escape(stamp(dates.max())) if len(dates) else 'Indisponibles') + '</dd>'
    used = data['detail'].snapshot_date.max() if data['historical_mode'] else pd.NaT
    body += '<dt>Snapshot utilisé pour cette valeur</dt><dd>' + (escape(stamp(used)) if data['historical_mode'] else 'Sans objet · quantités actuelles') + '</dd>'
    body += '<dt>Dernier snapshot de la période</dt><dd>' + escape(stamp(data['historical'].snapshot_date.max())) + '</dd></dl>'
    if data['historical_mode']:
        body += '<p>Quantités du dernier snapshot enregistré avant la fin de période. Aucun patrimoine actuel projeté dans le passé.</p>'
    else:
        body += '<p>Le patrimoine connu inclut les quantités conservées localement. Une observation publique visible ne prouve pas le patrimoine complet.</p>'
    body += '<p>' + link('categories', 'Voir les catégories et leur couverture') + ' · ' + link('item', 'Consulter un objet') + '</p></section>'
    return body
