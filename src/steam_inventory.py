"""Observe visible Steam inventories or replace explicitly complete owner holdings."""

import argparse
from hashlib import sha256
import json
import os
import re
from pathlib import Path
import tempfile

import pandas as pd

from collection_runtime import collection_lock
from portfolio_data import CATEGORIES, HOLDINGS, ROOT, _parse_dates, load_holdings, validate_holdings
from update_market_prices import validate_catalog
from cloud_inventory import auto_publish


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
    if not isinstance(export, dict) or type(export.get("schema")) is not int or export.get("schema") != 1 or export.get("complete") is not True:
        raise ValueError("Expected a fully paginated export; complete does not certify portfolio coverage")
    if pd.isna(timestamp(export.get("collected_at"))):
        raise ValueError("Missing export timestamp")
    if not isinstance(export.get("account_id"), str) or not export["account_id"].strip() or export["account_id"] != export["account_id"].strip():
        raise ValueError("Export requires an account_id; do not mix accounts")
    pages = export.get("pages")
    if not isinstance(pages, list) or not pages:
        raise ValueError("Missing inventory pages")
    assets, descriptions = {}, {}
    cursor = None
    cursors = set()
    def identifier(value):
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]+", value):
            raise ValueError("Expected explicit numeric Steam identity fields")
        return value
    for index, page in enumerate(pages):
        if not isinstance(page, dict) or type(page.get("success")) is not int or page.get("success") != 1 or page.get("start_assetid") != cursor:
            raise ValueError("Failed or discontinuous inventory page")
        more = page.get("more_items")
        if type(more) is not int or more not in (0, 1) or bool(more) != (index < len(pages)-1):
            raise ValueError("Incomplete pagination")
        cursor = page.get("last_assetid") if more else None
        if more:
            identifier(cursor)
            if cursor in cursors:
                raise ValueError("Repeated next page cursor")
            cursors.add(cursor)
        if not isinstance(page.get("assets"), list) or not isinstance(page.get("descriptions"), list):
            raise ValueError("Missing assets/descriptions, even for an empty inventory")
        for item in page["descriptions"]:
            if not isinstance(item, dict) or str(item.get("appid")) != "730":
                raise ValueError("Expected CS2 descriptions")
            key = (identifier(item.get("classid")), identifier(item.get("instanceid")))
            name = item.get("market_hash_name")
            if not isinstance(name, str) or not name.strip() or name != name.strip():
                raise ValueError("Missing exact market name")
            if key in descriptions and descriptions[key] != name:
                raise ValueError("Conflicting asset descriptions")
            descriptions[key] = name
        for asset in page["assets"]:
            if not isinstance(asset, dict) or str(asset.get("appid")) != "730" or str(asset.get("contextid")) != "2":
                raise ValueError("Expected CS2 context 2 assets")
            asset_id = identifier(asset.get("assetid"))
            amount = identifier(asset.get("amount"))
            if int(amount) <= 0:
                raise ValueError("Invalid Steam asset amount")
            normalized = dict(asset_id=asset_id, classid=identifier(asset.get("classid")),
                              instanceid=identifier(asset.get("instanceid")), quantity=int(amount))
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
    path = Path(root) / 'data/processed/steam_inventory_override.json'
    if path.exists():
        override = json.loads(path.read_text(encoding='utf-8'))
        basis = ('owner_declared_full_portfolio' if override.get('inventory_scope') == 'full_portfolio'
                 else 'legacy_override_coverage_unverified')
    else:
        basis = 'manual_csv'
    return dict(holdings=records, imported=sorted(imported), portfolio_basis=basis)


def export_selection(export):
    """Keep asset deduplication scoped to each explicitly selected account."""
    if not isinstance(export, dict):
        raise ValueError("Expected an inventory export object")
    if type(export.get('schema')) is not int:
        raise ValueError('Expected integer export schema')
    if export.get("schema") == 1:
        sources = [export]
    elif export.get("schema") == 2 and export.get("complete") is True:
        sources = export.get("accounts")
        if not isinstance(sources, list) or not sources:
            raise ValueError("Multi-account selection requires complete account exports")
    else:
        raise ValueError("Expected complete schema 1 export or schema 2 account selection")
    frames, dates = [], {}
    for source in sources:
        assets = parse_export(source)
        account = source["account_id"]
        if account in dates:
            raise ValueError("Duplicate account in inventory selection")
        dates[account] = source["collected_at"]
        frames.append(assets.assign(account_id=account))
    ids = sorted(dates)
    scope = ids[0] if len(ids) == 1 else "multi:" + digest(ids)
    return pd.concat(frames, ignore_index=True), ids, dates, scope


def coverage(export):
    """Missing legacy metadata never certifies full-portfolio coverage."""
    sources = [export] if export['schema'] == 1 else export['accounts']
    scopes, provenance = set(), {}
    for source in sources:
        scope = source.get('inventory_scope', 'visible')
        origin = source.get('source', 'steam_community')
        if scope not in ('visible', 'full_portfolio') or origin not in ('steam_community', 'owner_export'):
            raise ValueError('Unknown inventory scope or source')
        if scope == 'full_portfolio' and origin != 'owner_export':
            raise ValueError('Full portfolio requires an explicit owner_export including storage contents')
        scopes.add(scope)
        provenance[source['account_id']] = origin
    if len(scopes) != 1:
        raise ValueError('Do not mix visible and full-portfolio account exports')
    return scopes.pop(), provenance


def observation_differences(old, observed):
    """Compare a visible subset with global holdings without inferring transactions."""
    frame = old.merge(observed, on=HOLDINGS[:3], how='outer', suffixes=('_known', '_visible'))
    rows, known_ids = [], set(old.item_id)
    for row in frame.itertuples(index=False):
        known, visible = row.quantity_known, row.quantity_visible
        if pd.isna(visible):
            status = 'not_observed'
        elif pd.isna(known):
            status = 'known_total_unknown' if row.item_id in known_ids else 'newly_observed'
        elif visible < known:
            status = 'visible_below_known'
        elif visible > known:
            status = 'visible_exceeds_known'
        else:
            status = 'visible_matches_known'
        rows.append(dict(item_id=row.item_id, category=row.category, item_name=row.item_name,
                         quantity_known=None if pd.isna(known) else int(known),
                         quantity_visible=None if pd.isna(visible) else int(visible), status=status))
    return rows


def preview(export, catalog, root=ROOT):
    assets, account_ids, account_dates, account_scope = export_selection(export)
    inventory_scope, account_sources = coverage(export)
    validate_catalog(catalog, catalog.assign(quantity=0)[HOLDINGS])
    before = state(root)
    mapping = catalog[["market_hash_name", *HOLDINGS[:3]]]
    matched = assets.merge(mapping, on="market_hash_name", how="left", validate="many_to_one")
    unresolved = sorted(set(matched.loc[matched.item_id.isna(), "market_hash_name"]))
    known = matched.loc[matched.item_id.notna()]
    observed = known.groupby(HOLDINGS[:3], as_index=False).quantity.sum()[HOLDINGS]
    validate_holdings(observed)
    old = pd.DataFrame(before["holdings"], columns=HOLDINGS)
    # Public inventories exclude storage contents. They cannot replace or add to
    # global holdings: an apparent addition may be a transfer from another account.
    holdings = observed if inventory_scope == 'full_portfolio' else old.copy()
    changes = old.merge(holdings, on=HOLDINGS[:3], how="outer", suffixes=("_before", "_after"))
    # Only absent rows mean zero; existing unknown quantities stay unknown.
    changes.loc[~changes.item_id.isin(old.item_id), "quantity_before"] = 0
    changes.loc[~changes.item_id.isin(holdings.item_id), "quantity_after"] = 0
    changes["delta"] = changes.quantity_after - changes.quantity_before
    plan = dict(schema=1, source_hash=digest(export), collected_at=max(account_dates.values(), key=timestamp), account_id=account_scope,
                account_ids=account_ids, account_collected_at=account_dates,
                inventory_scope=inventory_scope, account_sources=account_sources,
                action='replace_portfolio' if inventory_scope == 'full_portfolio' else 'record_visible_observation',
                coverage_note=('Owner-declared full portfolio including storage; this is not independently verified.'
                               if inventory_scope == 'full_portfolio' else
                               'Visible items in the selected accounts only; storage and omitted accounts are not covered. '
                               'Missing items are not sales. Global quantities stay unchanged, including newly visible items. '
                               'Account captures may span transfers; no transfer or storage location is inferred.'),
                before_hash=digest(before), holdings=json.loads(holdings.to_json(orient="records")),
                portfolio_basis=before['portfolio_basis'],
                imported=list(CATEGORIES) if inventory_scope == 'full_portfolio' else before['imported'],
                observed_holdings=json.loads(observed.to_json(orient='records')),
                observation_differences=observation_differences(old, observed) if inventory_scope == 'visible' else [],
                unresolved=unresolved,
                assets=json.loads(matched.to_json(orient="records")),
                changes=json.loads(changes.to_json(orient="records")))
    accounts = []
    for account in account_ids:
        selected = matched.loc[matched.account_id.eq(account)]
        resolved = selected.loc[selected.item_id.notna()]
        quantities = resolved.groupby(HOLDINGS[:3], as_index=False).quantity.sum()[HOLDINGS]
        accounts.append(dict(account_id=account, collected_at=account_dates[account],
                             inventory_scope=inventory_scope, source=account_sources[account],
                             asset_count=len(selected), total_quantity=int(selected.quantity.sum()),
                             matched_quantity=int(resolved.quantity.sum()),
                             unresolved_quantity=int(selected.loc[selected.item_id.isna(), 'quantity'].sum()),
                             unresolved=sorted(set(selected.loc[selected.item_id.isna(), 'market_hash_name'])),
                             holdings=json.loads(quantities.to_json(orient='records'))))
    plan['accounts'] = accounts
    plan["review_token"] = digest(plan)
    return plan


def apply(export, catalog, token, root=ROOT, environment="school"):
    """Persist a reviewed observation or explicitly complete owner replacement."""
    if environment != "home":
        raise ValueError("school is read-only")
    root = Path(root)
    with collection_lock(root):
        plan = preview(export, catalog, root)
        if plan['inventory_scope'] == 'visible':
            value = _record_observation(plan, token, root)
            auto_publish(root)
            return value
        path = root / "data/processed/steam_inventory_override.json"
        previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        # Same source and current quantities: exact repetition is a no-op.
        if previous and previous.get("source_hash") == plan["source_hash"] and previous["holdings"] == plan["holdings"]:
            auto_publish(root)
            return previous
        if not isinstance(token, str) or token != plan["review_token"]:
            raise ValueError("Review token does not match current preview; preview again")
        if plan["unresolved"]:
            raise ValueError("Resolve unknown/unsupported market listings before applying")
        if previous:
            previous_ids = previous.get("account_ids", [previous["account_id"]])
            if sorted(previous_ids) != plan["account_ids"]:
                raise ValueError("Override account selection differs; restore before explicitly changing account scope")
            previous_dates = previous.get("account_collected_at", {previous["account_id"]: previous["collected_at"]})
            if any(timestamp(plan["account_collected_at"][account]) < timestamp(date) for account, date in previous_dates.items()):
                raise ValueError("Refusing an older inventory export for an account")
        backup = dict(schema=1, previous_override=previous, prior_effective=state(root), applied=plan)
        backup_key = digest(backup)
        backup_path = root / "data/imports" / f"{backup_key}.json"
        atomic_json(backup, backup_path)
        value = dict(schema=1, holdings=plan["holdings"], imported=plan["imported"],
                     inventory_scope=plan['inventory_scope'], account_sources=plan['account_sources'],
                     source_hash=plan["source_hash"], collected_at=plan["collected_at"],
                     account_id=plan["account_id"], account_ids=plan["account_ids"],
                     account_collected_at=plan["account_collected_at"], backup_id=backup_key)
        atomic_json(value, path)
        auto_publish(root)
        return value


def _record_observation(plan, token, root):
    """Persist one reviewed capture separately; never mutate portfolio overrides.

    Called under the import lock. Earlier captures are retained in the audit;
    account subsets replace the visible selection, never sum cached accounts.
    """
    path = root / 'data/processed/steam_inventory_visible.json'
    previous = json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
    value = dict(schema=1, inventory_scope='visible', source_hash=plan['source_hash'],
                 collected_at=plan['collected_at'], account_ids=plan['account_ids'],
                 account_collected_at=plan['account_collected_at'],
                 account_sources=plan['account_sources'], accounts=plan['accounts'],
                 observed_holdings=plan['observed_holdings'], unresolved=plan['unresolved'])
    # Same source can resolve differently after a reviewed catalog correction.
    if previous and all(previous.get(key) == item for key, item in value.items()):
        return previous
    if not isinstance(token, str) or token != plan['review_token']:
        raise ValueError('Review token does not match current preview; preview again')
    # Keep the most recent capture date even for accounts omitted this time.
    latest_dates = dict(previous.get('latest_account_collected_at', previous['account_collected_at'])) if previous else {}
    if any(account in latest_dates and timestamp(date) < timestamp(latest_dates[account])
           for account, date in plan['account_collected_at'].items()):
        raise ValueError('Refusing an older visible inventory export for an account')
    latest_dates.update(plan['account_collected_at'])
    audit = dict(schema=1, previous_observation=previous, applied=plan)
    key = digest(audit)
    atomic_json(audit, root / 'data/imports' / f'{key}.json')
    value.update(latest_account_collected_at=latest_dates, audit_id=key)
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
        auto_publish(root)


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
