"""Shared read-only coverage labels for summary, holdings and data-quality views."""

import pandas as pd

STALE_DAYS = 45
BASIS_LABELS = {
    'manual_csv': 'CSV locaux · date des quantités non documentée',
    'not_imported': 'Aucun inventaire importé',
    'owner_declared_full_portfolio': 'Export propriétaire déclaré complet',
    'legacy_override_coverage_unverified': 'Ancien remplacement · couverture non vérifiée',
    'recorded_snapshot': 'Snapshot enregistré',
}
PRICE_LABELS = {'missing': 'Prix absent', 'stale': 'Prix ancien', 'recent': 'Prix récent'}


def held_rows(detail, cutoff):
    """A zero position is not held; an unknown position stays visible as unknown."""
    rows = detail.loc[detail.state.eq('holdings') & (detail.quantity.isna() | detail.quantity.gt(0))].copy()
    rows['price_age_days'] = (pd.Timestamp(cutoff) - pd.to_datetime(rows.price_date)).dt.total_seconds() / 86400
    rows['price_status'] = rows.unit_price.map(lambda p: 'missing' if pd.isna(p) else 'recent')
    rows.loc[rows.unit_price.notna() & rows.price_age_days.gt(STALE_DAYS), 'price_status'] = 'stale'
    rows['quantity_status'] = rows.quantity.map(lambda q: 'unknown' if pd.isna(q) else 'known')
    rows['coverage_status'] = [
        'Quantité inconnue · ' + PRICE_LABELS[p].lower() if q == 'unknown' else PRICE_LABELS[p]
        for q, p in zip(rows.quantity_status, rows.price_status)]
    return rows


def coverage(data):
    rows = held_rows(data['detail'], data['cutoff'])
    total = data['current'].loc[data['current'].category.eq('global')]
    values = total.iloc[0].to_dict() if len(total) else {}
    unverified = data['provenance']['basis'] == 'legacy_override_coverage_unverified'
    missing_categories = int(values.get('categories_not_imported', 0))
    if total.empty:
        label = 'Aucun snapshot disponible' if data['historical_mode'] else 'Données indisponibles'
    elif missing_categories or rows.quantity_status.eq('unknown').any() or rows.price_status.eq('missing').any():
        label = 'Couverture partielle'
    elif unverified:
        label = 'Couverture non vérifiée'
    elif rows.empty:
        label = 'Inventaire importé vide'
    else:
        label = 'Couverture complète'
    return dict(rows=rows, held_items=len(rows), known_quantities=int(rows.quantity.notna().sum()),
                priced_items=int(rows.unit_price.notna().sum()), stale_items=int(rows.price_status.eq('stale').sum()),
                missing_categories=missing_categories, label=label, unverified=unverified,
                total_value=values.get('total_value', float('nan')), known_value=values.get('known_value', float('nan')))
