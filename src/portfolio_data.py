"""Shared identities and read-only loading for the complete portfolio."""

from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pandas as pd

from analyze_drop_cases import _parse_dates, _parse_numbers

CATEGORIES = ("case", "skin", "souvenir", "sticker", "charm", "agent")
FILES = {"drop_cases": "case", "skins": "skin", "souvenirs": "souvenir", "others": None}
ROOT = Path(__file__).resolve().parents[1]
HOLDINGS = ["item_id", "category", "item_name", "quantity"]
PRICES = ["date", "item_id", "category", "item_name", "unit_price", "source", "currency", "date_estimated"]


def identity(category, name):
    if category not in CATEGORIES or not isinstance(name, str) or not name or name != name.strip():
        raise ValueError("Expected a supported category and an exact, nonblank item name")
    return str(uuid5(NAMESPACE_URL, f"ckin2:{category}:{name}"))


def validate_holdings(frame):
    if not set(HOLDINGS).issubset(frame):
        raise ValueError("Missing holding columns")
    result = frame[HOLDINGS].copy()
    for row in result.itertuples(index=False):
        if row.item_id != identity(row.category, row.item_name):
            raise ValueError("Item identity does not match category and name")
    result["quantity"] = _parse_numbers(result.quantity, "quantity")
    if (result.quantity.dropna() % 1 != 0).any():
        raise ValueError("Quantities must be whole numbers or unknown")
    if result.item_id.duplicated().any():
        raise ValueError("Duplicate inventory identity")
    return result


def load_holdings(root=ROOT):
    frames, imported = [], set()
    for prefix, category in FILES.items():
        path = Path(root) / "data/processed" / f"{prefix}_inventory.csv"
        if not path.exists():
            continue
        frame = pd.read_csv(path).rename(columns={"case_name": "item_name"})
        if category:
            frame["category"] = category
            imported.add(category)
        else:
            if "item_type" not in frame:
                raise ValueError("others inventory requires item_type")
            frame["category"] = frame.item_type
            if not frame.category.isin(["sticker", "charm", "agent"]).all():
                raise ValueError("Unsupported category in others inventory")
            # An imported others file covers all three subcategories, including empty ones.
            imported.update(["sticker", "charm", "agent"])
        frame["item_id"] = [identity(c, n) for c, n in zip(frame.category, frame.item_name)]
        frames.append(frame[HOLDINGS])
    holdings = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=HOLDINGS)
    return validate_holdings(holdings), imported


def parse_flags(series):
    mapping = {True: True, False: False, "True": True, "False": False}
    if not series.map(lambda v: v in mapping if not pd.isna(v) else False).all():
        raise ValueError("date_estimated must be boolean")
    return series.map(mapping).astype(bool)


def validate_prices(frame):
    if not set(PRICES).issubset(frame):
        raise ValueError("Missing market price columns")
    result = frame[PRICES].copy()
    for row in result.itertuples(index=False):
        if row.item_id != identity(row.category, row.item_name):
            raise ValueError("Price identity mismatch")
    result["date"] = _parse_dates(result.date, "market date")
    result["unit_price"] = _parse_numbers(result.unit_price, "market price")
    result["date_estimated"] = parse_flags(result.date_estimated)
    if not result.currency.eq("EUR").all() or not result.source.isin(["steam", "legacy_csv"]).all():
        raise ValueError("Expected EUR market observations with a known source")
    return result


def load_prices(root=ROOT, holdings=None):
    """Legacy exports stay untouched; fresh observations live in their own file."""
    if holdings is None:
        holdings, _ = load_holdings(root)
    frames = []
    registry = holdings[["item_id", "category", "item_name"]].copy()
    catalog_path = Path(root) / "data/processed/market_catalog.csv"
    if catalog_path.exists():
        catalog = pd.read_csv(catalog_path)
        validate_holdings(catalog.assign(quantity=0)[HOLDINGS])
        registry = pd.concat([catalog[["item_id", "category", "item_name"]], registry], ignore_index=True)
    registry = registry.loc[registry.category.isin(["sticker", "charm", "agent"])]
    if registry.groupby("item_name").category.nunique().gt(1).any():
        raise ValueError("Ambiguous historical category for an others item")
    names = registry.drop_duplicates("item_name").set_index("item_name").category.to_dict()
    for prefix, category in FILES.items():
        path = Path(root) / "data/processed" / f"{prefix}_prices.csv"
        if not path.exists():
            continue
        frame = pd.read_csv(path).rename(columns={"case_name": "item_name"})
        if "source_column" in frame:
            markers = pd.to_numeric(frame.source_column, errors="raise")
            if markers.isna().any() or (markers < 0).any() or (markers % 1 != 0).any():
                raise ValueError("Invalid acquisition markers")
            frame = frame.loc[markers.ne(0)].copy()
        frame["category"] = category if category else frame.item_name.map(names)
        if frame.category.isna().any():
            raise ValueError("Cannot classify an others price without its inventory entry")
        frame["item_id"] = [identity(c, n) for c, n in zip(frame.category, frame.item_name)]
        frame["source"], frame["currency"] = "legacy_csv", "EUR"
        if "date_estimated" not in frame:
            frame["date_estimated"] = False
        frames.append(frame[PRICES])
    observed = Path(root) / "data/processed/market_observations.csv"
    if observed.exists():
        frames.append(pd.read_csv(observed))
    data = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=PRICES)
    return validate_prices(data)


def atomic_csv(frame, path):
    """Replace a single CSV only after the entire new file has been written."""
    import os
    import tempfile

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            frame.to_csv(stream, index=False)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
