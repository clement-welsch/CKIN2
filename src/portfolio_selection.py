"""Read-only portfolio selection shared by notebooks and dashboard."""

import json
from pathlib import Path

import pandas as pd

from global_snapshots import COLUMNS, value_snapshots
from portfolio_data import CATEGORIES, FILES, _parse_dates


def subset_snapshots(snapshots, categories, item_id):
    """Keep six explicit category markers so shared validation/valuation applies."""
    rows = []
    for stamp, group in snapshots.groupby("snapshot_date"):
        for category in CATEGORIES:
            selected = group.loc[group.category.eq(category)]
            if category not in categories:
                selected = selected.iloc[:0]
            elif item_id:
                selected = selected.loc[~selected.state.eq("holdings") | selected.item_id.eq(item_id)]
            if selected.empty:
                rows.append(dict(snapshot_date=stamp, category=category, state="empty", item_id=None, item_name=None, quantity=0))
            else:
                rows.extend(selected[COLUMNS].to_dict("records"))
    return pd.DataFrame(rows, columns=COLUMNS)



def selection(data, categories, *, item_id="", historical=False):
    """Select recorded holdings in historical mode, never today's quantities."""
    if historical:
        history = data["history"]
        snapshot = history.loc[history.snapshot_date.eq(history.snapshot_date.max())]
    else:
        snapshot = data["current_detail"][COLUMNS]
    return value_snapshots(subset_snapshots(snapshot, categories, item_id), data["prices"])


def quantity_provenance(root):
    """Report source timestamps only when recorded; file mtime is not capture time."""
    root = Path(root)
    path = root / "data/processed/steam_inventory_override.json"
    if path.exists():
        value = json.loads(path.read_text(encoding="utf-8"))
        return dict(basis=("owner_declared_full_portfolio" if value.get("inventory_scope") == "full_portfolio"
                           else "legacy_override_coverage_unverified"),
                    source=str(path), collected_at=value.get("collected_at"),
                    account_collected_at=value.get("account_collected_at", {}))
    sources = [str(root / "data/processed" / f"{prefix}_inventory.csv") for prefix in FILES
               if (root / "data/processed" / f"{prefix}_inventory.csv").exists()]
    return dict(basis="manual_csv" if sources else "not_imported", source=sources,
                collected_at=None, account_collected_at={})


def analysis_date(value=None):
    return _parse_dates(pd.Series([pd.Timestamp.now() if value is None else value]), "analysis date").iloc[0]
