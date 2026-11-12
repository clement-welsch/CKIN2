"""Compact, accessible summary over the shared portfolio valuation."""

from html import escape
from urllib.parse import urlencode

import pandas as pd

from dashboard_status import BASIS_LABELS, STALE_DAYS, coverage


def stamp(value):
    return str(value) if pd.notna(value) else 'Indisponible'


def money(value):
    return f'{value:,.2f} EUR' if pd.notna(value) else 'Indisponible'


def quantity_decrease_alert(data):
    """Compare known quantities with the last snapshot before the viewed month."""
    history = data.get('snapshots', pd.DataFrame())
    if history.empty or data['detail'].empty:
        return ''
    current = data['detail']
    when = current.snapshot_date.max() if data['historical_mode'] else data['cutoff']
    previous = history.loc[history.snapshot_date.lt(pd.Timestamp(when).to_period('M').start_time)]
    if previous.empty:
        return ''
    previous = previous.loc[previous.snapshot_date.eq(previous.snapshot_date.max())]
    available = set(previous.loc[previous.state.ne('not_imported'), 'category']) & set(current.loc[current.state.ne('not_imported'), 'category'])
    old = previous.loc[previous.state.eq('holdings') & previous.category.isin(available), ['item_id', 'item_name', 'quantity']]
    new = current.loc[current.state.eq('holdings') & current.category.isin(available), ['item_id', 'item_name', 'quantity']]
    compared = old.merge(new, on='item_id', how='outer', suffixes=('_old', '_new'), indicator=True)
    compared.loc[compared._merge.eq('left_only'), 'quantity_new'] = 0
    decreases = compared.loc[compared.quantity_new.lt(compared.quantity_old)]
    if decreases.empty:
        return ''
    rows = ''.join('<li>' + escape(str(row.item_name_old)) + ' : ' + f'{row.quantity_old:g} → {row.quantity_new:g}' + '</li>' for row in decreases.itertuples())
    return ('<section role="status" aria-label="Baisses de quantités à vérifier"><h2>Baisses de quantités à vérifier</h2>'
            '<p>Par rapport au relevé du ' + escape(str(previous.snapshot_date.max())) +
            '. Vérifiez ces écarts : ils peuvent correspondre à des ouvertures, des ventes ou des corrections. '
            'Cette alerte ne bloque pas la mise à jour.</p><ul>' + rows + '</ul></section>')


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
    quantity_unavailable = ('holdings' in data.get('errors', {}) and not data['historical_mode']) or ('history' in data.get('errors', {}) and data['historical_mode'])
    body += card('Objets distincts détenus ou de quantité inconnue', 'Indisponible' if quantity_unavailable else status['held_items']) + '</div>'
    if quantity_unavailable:
        body += '<p>Quantités et couverture : indisponibles tant que la source est invalide.</p>'
    else:
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
    body += '<p>' + link('inventory', 'Consulter l’inventaire détenu') + ' · ' + link('categories', 'Voir les catégories et leur couverture') + ' · ' + link('item', 'Consulter un objet') + ' · ' + link('quality', 'Vérifier la qualité des données') + '</p></section>'
    return body + quantity_decrease_alert(data)
