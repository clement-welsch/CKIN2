"""Preview complete local Steam exports; apply reviewed quantities atomically."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile

import pandas as pd

from collection_runtime import collection_lock
from portfolio_data import CATEGORIES, HOLDINGS, ROOT, _parse_dates, load_holdings, validate_holdings
from update_market_prices import validate_catalog


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def timestamp(value):
    return _parse_dates(pd.Series([value]), "Steam import timestamp").iloc[0]


def digest(value):
    return sha256(canonical(value).encode("utf-8")).hexdigest()


def atomic_json(value, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(canonical(value))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def parse_export(export):
    """Require a complete, cursor-linked app 730/context 2 local page chain."""
    if not isinstance(export, dict) or export.get("schema") != 1 or export.get("complete") is not True:
        raise ValueError("Only explicitly complete exports can replace inventory")
    timestamp(export["collected_at"])
    if not isinstance(export.get("account_id"), str) or not export["account_id"].strip():
        raise ValueError("Export requires an account_id; do not mix accounts")
    pages = export.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("Missing inventory pages")
    assets, descriptions = {}, {}
    cursor = None
    for index, page in enumerate(pages):
        if page.get("success") != 1 or page.get("start_assetid") != cursor:
            raise ValueError("Failed or discontinuous inventory page")
        more = page.get("more_items")
        if type(more) is not int or more not in (0, 1) or bool(more) != (index < len(pages)-1):
            raise ValueError("Incomplete pagination")
        cursor = page.get("last_assetid") if more else None
        if more and (not isinstance(cursor, str) or not cursor):
            raise ValueError("Missing next page cursor")
        if not isinstance(page.get("assets"), list) or not isinstance(page.get("descriptions"), list):
            raise ValueError("Missing assets/descriptions, even for an empty inventory")
        for item in page["descriptions"]:
            if str(item.get("appid")) != "730":
                raise ValueError("Expected CS2 descriptions")
            key = (str(item.get("classid")), str(item.get("instanceid")))
            name = item.get("market_hash_name")
            if not isinstance(name, str) or not name.strip() or name != name.strip():
                raise ValueError("Missing exact market name")
            if key in descriptions and descriptions[key] != name:
                raise ValueError("Conflicting asset descriptions")
            descriptions[key] = name
        for asset in page["assets"]:
            if str(asset.get("appid")) != "730" or str(asset.get("contextid")) != "2":
                raise ValueError("Expected CS2 context 2 assets")
            asset_id = asset.get("assetid")
            if not isinstance(asset_id, str) or not asset_id.isdigit():
                raise ValueError("Invalid asset ID")
            amount = asset.get("amount")
            if not isinstance(amount, str) or not amount.isdigit() or int(amount) <= 0:
                raise ValueError("Invalid Steam asset amount")
            normalized = dict(asset_id=asset_id, classid=str(asset.get("classid")),
                              instanceid=str(asset.get("instanceid")), quantity=int(amount))
            if asset_id in assets and assets[asset_id] != normalized:
                raise ValueError("Conflicting duplicate asset")
            assets[asset_id] = normalized
    rows = []
    for asset in assets.values():
        name = descriptions.get((asset["classid"], asset["instanceid"]))
        if name is None:
            raise ValueError("Asset description is absent")
        rows.append(dict(**asset, market_hash_name=name))
    return pd.DataFrame(rows, columns=["asset_id", "classid", "instanceid", "quantity", "market_hash_name"])


def state(root):
    holdings, imported = load_holdings(root)
    # Quantities unknown in legacy holdings must remain JSON null, not NaN.
    records = json.loads(holdings.sort_values("item_id").to_json(orient="records"))
    return dict(holdings=records, imported=sorted(imported))


def preview(export, catalog, root=ROOT):
    assets = parse_export(export)
    validate_catalog(catalog, catalog.assign(quantity=0)[HOLDINGS])
    before = state(root)
    mapping = catalog[["market_hash_name", *HOLDINGS[:3]]]
    matched = assets.merge(mapping, on="market_hash_name", how="left", validate="many_to_one")
    unresolved = sorted(set(matched.loc[matched.item_id.isna(), "market_hash_name"]))
    known = matched.loc[matched.item_id.notna()]
    holdings = known.groupby(HOLDINGS[:3], as_index=False).quantity.sum()[HOLDINGS]
    validate_holdings(holdings)
    old = pd.DataFrame(before["holdings"], columns=HOLDINGS)
    changes = old.merge(holdings, on=HOLDINGS[:3], how="outer", suffixes=("_before", "_after"))
    # Only absent rows mean zero; existing unknown quantities stay unknown.
    changes.loc[~changes.item_id.isin(old.item_id), "quantity_before"] = 0
    changes.loc[~changes.item_id.isin(holdings.item_id), "quantity_after"] = 0
    changes["delta"] = changes.quantity_after - changes.quantity_before
    plan = dict(schema=1, source_hash=digest(export), collected_at=export["collected_at"], account_id=export["account_id"],
                before_hash=digest(before), holdings=json.loads(holdings.to_json(orient="records")),
                imported=list(CATEGORIES), unresolved=unresolved,
                assets=json.loads(matched.to_json(orient="records")),
                changes=json.loads(changes.to_json(orient="records")))
    plan["review_token"] = digest(plan)
    return plan


def apply(export, catalog, token, root=ROOT, environment="school"):
    """Recompute the displayed plan, rejecting stale inputs or incomplete matches."""
    if environment != "home":
        raise ValueError("school is read-only")
    root = Path(root)
    with collection_lock(root):
        plan = preview(export, catalog, root)
        path = root / "data/processed/steam_inventory_override.json"
        previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        # Same source and current quantities: exact repetition is a no-op.
        if previous and previous.get("source_hash") == plan["source_hash"] and previous["holdings"] == plan["holdings"]:
            return previous
        if not isinstance(token, str) or token != plan["review_token"]:
            raise ValueError("Review token does not match current preview; preview again")
        if plan["unresolved"]:
            raise ValueError("Resolve unknown/unsupported market listings before applying")
        if previous and previous.get("account_id") != plan["account_id"]:
            raise ValueError("Override belongs to another account; multi-account merge requires explicit preparation")
        if previous and timestamp(plan["collected_at"]) < timestamp(previous["collected_at"]):
            raise ValueError("Refusing an older inventory export")
        backup = dict(schema=1, previous_override=previous, prior_effective=state(root), applied=plan)
        backup_key = digest(backup)
        backup_path = root / "data/imports" / f"{backup_key}.json"
        atomic_json(backup, backup_path)
        value = dict(schema=1, holdings=plan["holdings"], imported=plan["imported"],
                     source_hash=plan["source_hash"], collected_at=plan["collected_at"],
                     account_id=plan["account_id"], backup_id=backup_key)
        atomic_json(value, path)
        return value


def restore(root=ROOT, environment="school"):
    if environment != "home":
        raise ValueError("school is read-only")
    root = Path(root)
    with collection_lock(root):
        path = root / "data/processed/steam_inventory_override.json"
        current = json.loads(path.read_text(encoding="utf-8"))
        key = current["backup_id"]
        if not isinstance(key, str) or len(key) != 64 or any(c not in "0123456789abcdef" for c in key):
            raise ValueError("Invalid backup reference")
        backup = json.loads((root / "data/imports" / f"{key}.json").read_text(encoding="utf-8"))
        if digest(backup) != key:
            raise ValueError("Backup integrity mismatch")
        previous = backup["previous_override"]
        if previous is None:
            path.unlink()
        else:
            atomic_json(previous, path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("environment", choices=["school", "home"])
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--export", type=Path)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--apply-token", help="Exact review token from the displayed preview")
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    if args.restore:
        restore(args.root, args.environment)
    else:
        if not args.export or not args.catalog:
            parser.error("--export and --catalog required")
        export = json.loads(args.export.read_text(encoding="utf-8"))
        catalog = pd.read_csv(args.catalog)
        if args.apply_token:
            print(canonical(apply(export, catalog, args.apply_token, args.root, args.environment)))
        else:
            print(json.dumps(preview(export, catalog, args.root), ensure_ascii=False, indent=2))
