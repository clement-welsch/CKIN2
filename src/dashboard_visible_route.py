"""Read-only reconciliation of current known holdings and one visible capture."""

import html
import json
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd

from portfolio_data import HOLDINGS, ROOT, load_holdings, validate_holdings
from dashboard_categories import LABELS
from steam_inventory import observation_differences, state, timestamp

STATUS = {
    'not_observed': 'Non observé — quantité visible inconnue',
    'known_total_unknown': 'Total connu inconnu',
    'newly_observed': 'Nouvellement observé',
    'visible_below_known': 'Visible inférieur au connu',
    'visible_exceeds_known': 'Visible supérieur au connu',
    'visible_matches_known': 'Concordant',
}
SOURCES = {'steam_community': 'Inventaire public Steam', 'owner_export': 'Export propriétaire visible'}
BASES = {'manual_csv': 'Quantités des CSV locaux ; date de saisie non renseignée',
         'owner_declared_full_portfolio': 'Remplacement complet déclaré par le propriétaire (non vérifié indépendamment)',
         'legacy_override_coverage_unverified': 'Ancien remplacement : couverture non vérifiée'}


def visible_capture(root):
    """Validate the current capture; audits and cached past accounts are never summed."""
    path = Path(root) / 'data/processed/steam_inventory_visible.json'
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        if value['schema'] != 1 or value['inventory_scope'] != 'visible':
            raise ValueError('Expected a visible capture')
        ids = value['account_ids']
        if (not isinstance(ids, list) or not ids or
                any(not isinstance(a, str) or not a.strip() for a in ids) or len(set(ids)) != len(ids)):
            raise ValueError('Invalid account selection')
        accounts = value['accounts']
        if not isinstance(accounts, list) or len(accounts) != len(ids) or {a['account_id'] for a in accounts} != set(ids):
            raise ValueError('Missing account breakdown')
        frames = []
        for account in accounts:
            key = account['account_id']
            if (account['inventory_scope'] != 'visible' or account['source'] not in SOURCES or
                    value['account_sources'][key] != account['source'] or
                    pd.isna(timestamp(account['collected_at'])) or
                    timestamp(account['collected_at']) != timestamp(value['account_collected_at'][key])):
                raise ValueError('Invalid account provenance')
            holdings = validate_holdings(pd.DataFrame(account['holdings'], columns=HOLDINGS))
            if holdings.quantity.isna().any() or holdings.quantity.le(0).any():
                raise ValueError('Visible holdings require positive known quantities')
            if not isinstance(account['unresolved'], list) or any(not isinstance(n, str) for n in account['unresolved']):
                raise ValueError('Invalid unresolved listings')
            frames.append(holdings)
        combined = pd.concat(frames, ignore_index=True).groupby(HOLDINGS[:3], as_index=False).quantity.sum()[HOLDINGS]
        declared = validate_holdings(pd.DataFrame(value['observed_holdings'], columns=HOLDINGS))
        pd.testing.assert_frame_equal(combined.sort_values('item_id').reset_index(drop=True),
                                      declared.sort_values('item_id').reset_index(drop=True), check_dtype=False)
        if timestamp(value['collected_at']) != max(timestamp(a['collected_at']) for a in accounts):
            raise ValueError('Invalid capture date')
        latest_dates = value.get('latest_account_collected_at', {})
        if not isinstance(latest_dates, dict):
            raise ValueError('Invalid cached account dates')
        for key, date in latest_dates.items():
            if not isinstance(key, str) or pd.isna(timestamp(date)):
                raise ValueError('Invalid cached account date')
        return value
    except (KeyError, TypeError, AssertionError, ValueError) as error:
        raise ValueError('Observation visible locale invalide ; refaire une prévisualisation de l’export avant de l’enregistrer.') from error


def reconcile(root=ROOT, account=''):
    root = Path(root)
    holdings, _ = load_holdings(root)
    basis = state(root)['portfolio_basis']
    override_path = root / 'data/processed/steam_inventory_override.json'
    known_date = json.loads(override_path.read_text(encoding='utf-8')).get('collected_at') if override_path.exists() else None
    capture = visible_capture(root)
    if not capture:
        if account:
            raise ValueError('Compte absent de la capture actuelle')
        return dict(rows=[], accounts=[], omitted={}, capture=None, basis=basis, known_date=known_date, staggered=False)
    if account and account not in capture['account_ids']:
        raise ValueError('Compte absent de la capture actuelle ; les anciennes captures ne sont pas additionnées')
    selected = [a for a in capture['accounts'] if not account or a['account_id'] == account]
    frames = [pd.DataFrame(a['holdings'], columns=HOLDINGS) for a in selected]
    observed = pd.concat(frames, ignore_index=True).groupby(HOLDINGS[:3], as_index=False).quantity.sum()[HOLDINGS]
    observed = validate_holdings(observed)
    rows = observation_differences(holdings, observed)
    selected_ids = {a['account_id'] for a in selected}
    omitted = {key: date for key, date in capture.get('latest_account_collected_at', {}).items() if key not in selected_ids}
    for a in capture['accounts']:
        if a['account_id'] not in selected_ids:
            omitted[a['account_id']] = a['collected_at']
    return dict(rows=rows, accounts=selected, omitted=omitted, capture=capture, basis=basis,
                known_date=known_date, staggered=len({timestamp(a['collected_at']) for a in selected}) > 1)


def render_reconciliation(root=ROOT, params=None):
    params = params or {}
    if set(params) - {'account'}:
        raise ValueError('Filtre inconnu pour le rapprochement actuel')
    account = params.get('account', '')
    data = reconcile(root, account)
    esc = lambda value: html.escape(str(value), quote=True)
    body = '<p>Patrimoine connu : ' + esc(BASES[data['basis']]) + '. Date de capture propriétaire : ' + esc(data['known_date'] or 'Non renseignée') + '.</p>'
    body += '<p>Comparaison actuelle avec une capture visible locale, sans filtre historique. Un seul patrimoine global ; aucune quantité visible n’est ajoutée au patrimoine.</p>'
    body += '<p>Les unités de stockage et les comptes omis ne sont pas couverts. Non observé signifie inconnu, jamais vendu ou quantité zéro.</p>'
    if not data['capture']:
        body += '<h2>Aucune observation visible enregistrée</h2><p>Importer et valider explicitement un export visible avec la commande locale existante. Cette page ne collecte rien.</p>'
    else:
        options = '<option value="">Tous les comptes de cette capture</option>' + ''.join(
            '<option value="' + esc(key) + '"' + (' selected' if key == account else '') + '>' + esc(key) + '</option>' for key in data['capture']['account_ids'])
        body += '<form method="get"><label for="account">Comptes observés</label><select id="account" name="account">' + options + '</select><button>Comparer</button></form>'
        body += '<h2>Sources de la sélection</h2><ul>' + ''.join('<li>' + esc(a['account_id']) + ' · ' + esc(a['collected_at']) + ' · ' + esc(SOURCES[a['source']]) + ' · périmètre visible</li>' for a in data['accounts']) + '</ul>'
        if data['omitted']:
            body += '<p>Comptes omis de cette comparaison (dates conservées uniquement, quantités exclues) : ' + '; '.join(esc(key) + ' · ' + esc(date) for key, date in sorted(data['omitted'].items())) + '.</p>'
        body += '<p>Une capture pendant un transfert peut compter un objet deux fois ou ne pas le voir. Aucun transfert n’est identifié automatiquement.</p>'
        if data['staggered']:
            body += '<p><strong>Dates de capture décalées :</strong> la somme visible ne représente pas un état simultané.</p>'
        for a in data['accounts']:
            if a['unresolved']:
                body += '<p>Correspondances non résolues pour ' + esc(a['account_id']) + ' (exclues du rapprochement) : ' + ', '.join(esc(n) for n in a['unresolved']) + '.</p>'
        body += '<h2>Quantités connues et visibles</h2>'
        if not data['rows']:
            body += '<p>Aucun objet connu ni objet visible rapproché. Une capture vide ne prouve pas un patrimoine vide.</p>'
        else:
            body += '<p>Sur petit écran, faire défiler le tableau horizontalement ; au clavier, placer le focus sur le tableau puis utiliser les flèches.</p>'
            body += '<div class="table" role="region" aria-label="Comparaison des quantités" tabindex="0"><table><caption>Identités exactes ; les quantités inconnues restent indisponibles</caption><thead><tr><th scope="col">Objet</th><th scope="col">Catégorie</th><th scope="col">Quantité connue</th><th scope="col">Quantité visible</th><th scope="col">Statut</th></tr></thead><tbody>'
            for row in sorted(data['rows'], key=lambda r: (r['category'], r['item_name'], r['item_id'])):
                url = '/?' + urlencode({'page': 'item', 'category': row['category'], 'item_id': row['item_id']})
                body += '<tr><td><a href="' + esc(url) + '">' + esc(row['item_name']) + '</a></td><td>' + esc(LABELS[row['category']]) + '</td>'
                body += ''.join('<td>' + (str(row[key]) if row[key] is not None else 'Inconnue') + '</td>' for key in ('quantity_known', 'quantity_visible'))
                body += '<td>' + esc(STATUS[row['status']]) + '</td></tr>'
            body += '</tbody></table></div>'
    return '''<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>CKIN2 · Rapprochement</title><style>
body{margin:0;background:#101720;color:#e6edf5;font:16px/1.6 system-ui,sans-serif}main{max-width:1200px;margin:auto;padding:24px}a{color:#f8b55c}form{display:flex;gap:12px;flex-wrap:wrap;align-items:center}select,button{font:inherit;max-width:100%;padding:10px}table{border-collapse:collapse;width:100%}td,th{padding:12px;border-bottom:1px solid #526079;text-align:left}.table{overflow:auto}caption{text-align:left}a:focus-visible,select:focus-visible,button:focus-visible,.table:focus-visible{outline:3px solid #f8b55c;outline-offset:3px}@media(max-width:650px){main{padding:14px}form{display:grid}td,th{min-width:100px}}
</style></head><body><main><a href="/">Retour au portefeuille</a><h1>Patrimoine connu et inventaire visible</h1><p>Lecture seule · fichiers locaux · aucune collecte ni modification</p>''' + body + '</main></body></html>'
