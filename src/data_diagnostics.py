"""Explicit read-only failure boundaries; rejected datasets never yield totals."""

import pandas as pd

DATA_ERRORS = (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError)


def read_dataset(errors, name, loader, fallback, *, strict=False):
    try:
        return loader()
    except DATA_ERRORS:
        if strict:
            raise
        errors[name] = 'Données invalides ou illisibles'
        return fallback


def unavailable_valuation(detail, summary):
    detail, summary = detail.copy(), summary.copy()
    for column in ('market_value', 'unit_price', 'price_age_days'):
        detail[column] = float('nan')
    detail['price_date'] = pd.NaT
    for column in ('known_value', 'total_value'):
        summary[column] = float('nan')
    return detail, summary
