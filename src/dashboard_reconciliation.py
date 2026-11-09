"""Read-only comparison of one recorded visible selection with known holdings."""

import json
from html import escape
from pathlib import Path

import pandas as pd

from dashboard_status import BASIS_LABELS
from portfolio_data import HOLDINGS, validate_holdings
from steam_inventory import observation_differences, timestamp

STATUS_LABELS = {
    'not_observed': 'Non observé · quantité visible inconnue',
    'known_total_unknown': 'Total connu inconnu',
    'newly_observed': 'Nouvellement observé · sans quantité patrimoniale déduite',
    'visible_below_known': 'Visible inférieur au connu',
    'visible_exceeds_known': 'Visible supérieur au connu',
    'visible_matches_known': 'Concordant sur le périmètre visible',
}


def visible_holdings(records):
    if not isinstance(records, list) or any(not isinstance(r, dict) or not set(HOLDINGS).issubset(r) for r in records):
        raise ValueError('Invalid visible holding records')
    frame = validate_holdings(pd.DataFrame(records, columns=HOLDINGS))
    if frame.quantity.isna().any() or frame.quantity.le(0).any():
        raise ValueError('Visible holdings require positive observed quantities')
    return frame


def read_observation(root, cutoff):
    """Read only the latest explicit selection; never accumulate cached accounts."""
    path = Path(root) / 'data/processed/steam_inventory_visible.json'
    if not path.exists():
        return None
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict) or type(value.get('schema')) is not int or value['schema'] != 1 or value.get('inventory_scope') != 'visible':
        raise ValueError('Invalid visible observation schema/scope')
    ids, accounts = value.get('account_ids'), value.get('accounts')
    if not isinstance(ids, list) or not ids or any(not isinstance(i, str) or not i.strip() for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('Invalid visible account selection')
    if not isinstance(accounts, list) or len(accounts) != len(ids) or any(not isinstance(a, dict) for a in accounts):
        raise ValueError('Invalid visible account records')
    if {a.get('account_id') for a in accounts} != set(ids):
        raise ValueError('Visible account selection mismatch')
    frames, dates = [], []
    for account in accounts:
        stamp = timestamp(account['collected_at'])
        if account.get('inventory_scope') != 'visible' or account.get('source') not in ('steam_community', 'owner_export'):
            raise ValueError('Invalid visible account source')
        if timestamp(value['account_collected_at'][account['account_id']]) != stamp:
            raise ValueError('Conflicting visible account dates')
        if value['account_sources'][account['account_id']] != account['source']:
            raise ValueError('Conflicting visible account source')
        unresolved = account.get('unresolved')
        if not isinstance(unresolved, list) or any(not isinstance(n, str) for n in unresolved):
            raise ValueError('Invalid unresolved visible listings')
        frames.append(visible_holdings(account['holdings']))
        dates.append(stamp)
    combined = pd.concat(frames, ignore_index=True).groupby(HOLDINGS[:3], as_index=False).quantity.sum()[HOLDINGS]
    observed = visible_holdings(value['observed_holdings'])
    expected = combined.sort_values('item_id').reset_index(drop=True)
    actual = observed.sort_values('item_id').reset_index(drop=True)
    if expected[HOLDINGS[:3]].to_dict('records') != actual[HOLDINGS[:3]].to_dict('records') or expected.quantity.tolist() != actual.quantity.tolist():
        raise ValueError('Conflicting visible selection totals')
    if timestamp(value['collected_at']) != max(dates):
        raise ValueError('Conflicting visible capture date')
    if max(dates) > pd.Timestamp(cutoff):
        return None  # No reconstruction from audit/cached accounts at a past cutoff.
    value['observed'] = observed
    return value


def reconciliation(root, data, account='all'):
    capture = read_observation(root, data['cutoff'])
    if capture is None:
        return dict(capture=None, rows=pd.DataFrame(), accounts=[], omitted=[], mismatched_dates=False)
    if account != 'all' and account not in capture['account_ids']:
        raise ValueError('Select an account from the current visible capture')
    accounts = [a for a in capture['accounts'] if account == 'all' or a['account_id'] == account]
    observed = capture['observed'] if account == 'all' else visible_holdings(accounts[0]['holdings'])
    known = data['detail'].loc[data['detail'].state.eq('holdings'), HOLDINGS]
    rows = pd.DataFrame(observation_differences(known, observed))
    if rows.empty:
        rows = pd.DataFrame(columns=[*HOLDINGS[:3], 'quantity_known', 'quantity_visible', 'status'])
    rows = rows.loc[rows.category.isin(data['categories'])]
    if data['selected_item_id']:
        rows = rows.loc[rows.item_id.eq(data['selected_item_id'])]
    omitted = sorted(set(capture.get('latest_account_collected_at', {})) - {a['account_id'] for a in accounts})
    omitted = sorted(set(omitted) | (set(capture['account_ids']) - {a['account_id'] for a in accounts}))
    dates = {timestamp(a['collected_at']) for a in accounts}
    return dict(capture=capture, rows=rows, accounts=accounts, omitted=omitted, mismatched_dates=len(dates)>1)


def reconciliation_page(root, data, params, account, table):
    result = reconciliation(root, data, account)
    body = '<section><h2>Patrimoine connu et inventaire visible</h2>'
    body += '<p>Un seul patrimoine global. Les unités de stockage et les comptes omis ne sont pas couverts par la vue publique. '
    body += 'Une absence reste inconnue : elle ne signifie ni quantité nulle, ni vente.</p>'
    body += '<p>Quantités connues : ' + escape(BASIS_LABELS[data['provenance']['basis']]) + ' · date : ' + escape(str(data['provenance'].get('collected_at') or 'Non documentée')) + '</p>'
    if result['capture'] is None:
        return body + '<p class="empty">Aucune observation visible disponible à cette date. Importer explicitement un export local via steam_inventory.py en mode observation visible.</p></section>'
    body += '<form method="get"><input type="hidden" name="page" value="reconciliation">'
    body += ''.join('<input type="hidden" name="' + k + '" value="' + escape(str(v), quote=True) + '">' for k,v in params.items())
    choices = [('all', 'Tous les comptes de cette sélection')] + [(i,i) for i in result['capture']['account_ids']]
    body += '<label>Comptes observés<select name="observation_account">' + ''.join('<option value="' + escape(i,quote=True) + '"' + (' selected' if i==account else '') + '>' + escape(label) + '</option>' for i,label in choices) + '</select></label><button>Comparer</button></form>'
    body += '<p>Capture sélectionnée : ' + escape(str(result['capture']['collected_at'])) + '. Les captures mises en cache ne sont jamais additionnées.</p>'
    if result['omitted']:
        body += '<p>Comptes omis de cette comparaison : ' + escape(', '.join(result['omitted'])) + '. Leurs quantités visibles sont inconnues.</p>'
    if result['mismatched_dates']:
        body += '<p>Dates de capture décalées entre comptes.</p>'
    body += '<p>Un transfert pendant les captures peut produire un écart ou un double comptage apparent. Aucun transfert ni contenu stocké ne peut être identifié automatiquement.</p>'
    metadata = pd.DataFrame([{'Compte':a['account_id'],'Date de capture':a['collected_at'],'Source':a['source'], 'Correspondances non résolues':', '.join(a['unresolved']) or 'Aucune'} for a in result['accounts']])
    body += table(metadata)
    rows = result['rows'].copy()
    rows['status'] = rows.status.map(STATUS_LABELS)
    rows = rows.rename(columns={'item_name':'Objet','category':'Catégorie','quantity_known':'Quantité connue','quantity_visible':'Quantité visible','status':'Rapprochement'})
    body += table(rows[['Objet','Catégorie','Quantité connue','Quantité visible','Rapprochement']])
    return body + '</section>'
