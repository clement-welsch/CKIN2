"""Read-only notebook access to the dashboard's selection and valuation contract."""

from pathlib import Path

import pandas as pd

from dashboard import view
from dashboard_categories import category_data
from portfolio_data import ROOT


def portfolio_report(root=ROOT, *, category="all", item_id="", start=None, end=None,
                     now=None, components="overview"):
    """Use exactly the dashboard filters, including historical quantity selection.

    Prediction and acquisition references are opt-in, just as on their dashboard
    pages. Reading a report never collects prices or persists a snapshot.
    """
    root = Path(root).resolve()
    data = view(root, category=category, item_id=item_id, start=start, end=end,
                now=now, components=components)
    provenance_rows = (data["prices"].dropna(subset=["unit_price"])
                       .sort_values("date", kind="stable")
                       .drop_duplicates(["item_id", "date"], keep="last")
                       [["item_id", "date", "date_estimated", "source"]]
                       .rename(columns={"date": "price_date", "date_estimated": "price_date_estimated",
                                        "source": "price_source"}))
    provenance_rows["item_id"] = provenance_rows.item_id.astype(object)
    detail = data["detail"].copy()
    detail["price_date"] = pd.to_datetime(detail.price_date)
    data["current_detail"] = detail.merge(provenance_rows, on=["item_id", "price_date"],
                                         how="left", validate="many_to_one")
    override = root / "data/processed/steam_inventory_override.json"
    provenance = "CSV locaux du patrimoine"
    if override.exists():
        import json
        owner = json.loads(override.read_text(encoding="utf-8"))
        verified = owner.get("inventory_scope") == "full_portfolio"
        provenance = ("Remplacement propriétaire complet" if verified else
                      "Ancien remplacement propriétaire : provenance de couverture non vérifiée")
    if data["historical_mode"]:
        provenance = "Quantités historiques du dernier snapshot avant la fin sélectionnée"
    data["context"] = pd.DataFrame([{
        "data_root": str(root), "analysis_date": data["cutoff"],
        "category": category, "item_id": item_id, "start": start,
        "quantity_source": provenance,
        "scope": "Patrimoine connu ; observations publiques visibles exclues des quantités",
    }])
    return data


def category_reports(root, data, start=None):
    """Acquisition references remain separate from the canonical market prices."""
    return category_data(Path(root), data, pd.Timestamp(start) if start else None)
