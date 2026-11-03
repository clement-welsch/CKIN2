"""Immutable one-month forecast issues and read-only realized-error tracking."""

import argparse
from hashlib import sha256
import importlib.metadata
import json
import math
import os
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd

from portfolio_data import CATEGORIES, ROOT, _parse_dates, load_holdings, load_prices, validate_prices
from prediction import experiment

METHODS = ("persistence", "trend", "ridge")
SCHEMA = 1


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return sha256(canonical(value).encode("utf-8")).hexdigest()


def stamp(value):
    return _parse_dates(pd.Series([value]), "archive timestamp").iloc[0]


def month_close(value):
    return pd.Timestamp(value).normalize() + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)


def archive_key(record):
    return digest({key: record[key] for key in ("kind", "origin", "category", "revision")})


def settings(record):
    return {k: v for k, v in record["parameters"].items() if k != "information_cutoff"}


def validate_record(record):
    required = {"schema", "kind", "origin", "target_date", "emitted_at", "category", "revision",
                "archive_id", "payload_hash", "basket", "base_date", "parameters", "code_hash",
                "data_hash", "software", "predictions", "training_pairs", "training_end", "horizon_months"}
    if not isinstance(record, dict) or not required.issubset(record):
        raise ValueError("Missing forecast archive fields")
    if record["schema"] != SCHEMA or record["kind"] not in ("issued", "retrospective") or record["category"] not in (*CATEGORIES, "global"):
        raise ValueError("Unknown forecast schema, kind or category")
    if type(record["revision"]) is not int or record["revision"] < 1 or record["horizon_months"] != 1:
        raise ValueError("Expected positive revision and one-month horizon")
    if record["archive_id"] != archive_key(record) or record["payload_hash"] != digest({k: v for k, v in record.items() if k != "payload_hash"}):
        raise ValueError("Forecast archive integrity mismatch")
    origin, target, emitted, base = [stamp(record[k]) for k in ("origin", "target_date", "emitted_at", "base_date")]
    if origin != origin.normalize() + pd.offsets.MonthEnd(0) or target != origin + pd.offsets.MonthEnd(1) or base > origin:
        raise ValueError("Invalid forecast origin/base/target")
    if record["training_end"] is not None and stamp(record["training_end"]) > origin:
        raise ValueError("Training target exceeds origin")
    information_cutoff = stamp(record["parameters"]["information_cutoff"])
    if not month_close(origin) < information_cutoff <= emitted:
        raise ValueError("Invalid information cutoff")
    age = record["parameters"]["max_age_days"]
    if isinstance(age, bool) or not isinstance(age, (int, float)) or not math.isfinite(age) or age < 0:
        raise ValueError("Invalid price freshness policy")
    if emitted <= month_close(origin) or (record["kind"] == "issued" and emitted > month_close(target)):
        raise ValueError("Issued forecasts must follow origin close and precede target close")
    basket = record["basket"]
    if not basket or len({b["item_id"] for b in basket}) != len(basket):
        raise ValueError("Expected a nonempty unique frozen basket")
    for entry in basket:
        if not math.isfinite(entry["base_price"]) or entry["base_price"] <= 0 or not math.isfinite(entry["weight"]) or entry["weight"] <= 0:
            raise ValueError("Basket bases and weights must be finite and positive")
    if not math.isclose(sum(b["weight"] for b in basket), 1):
        raise ValueError("Basket weights must sum to one")
    if set(record["predictions"]) != set(METHODS) or any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0
            for v in record["predictions"].values() if v is not None):
        raise ValueError("Invalid forecast values")
    return record


def records(directory):
    result = []
    for path in sorted(Path(directory).glob("*.json")):
        record = validate_record(json.loads(path.read_text(encoding="utf-8")))
        if path.stem != record["archive_id"]:
            raise ValueError("Archive filename/key mismatch")
        result.append(record)
    return result


def save_record(record, directory):
    """Publish a complete file exclusively; Windows rename never replaces a target."""
    validate_record(record)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (record["archive_id"] + ".json")
    fd, temporary = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(canonical(record) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        try:
            if os.name == "nt":
                os.rename(temporary, target)
            else:
                os.link(temporary, target)
        except FileExistsError:
            previous = validate_record(json.loads(target.read_text(encoding="utf-8")))
            ignored = {"emitted_at", "payload_hash"}
            def semantic(value):
                return {**{k: v for k, v in value.items() if k not in ignored}, "parameters": settings(value)}
            if semantic(previous) != semantic(record):
                raise ValueError("Existing forecast differs; supply a new explicit revision")
            return previous
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return record


def issue(root=ROOT, *, revision=1, retrospective_as_of=None, min_train=12,
          max_age_days=45, clock=pd.Timestamp.now):
    root = Path(root)
    emitted = stamp(clock())
    cutoff = emitted if retrospective_as_of is None else stamp(retrospective_as_of)
    if cutoff > emitted:
        raise ValueError("Cannot simulate information from the future")
    if type(revision) is not int or revision < 1:
        raise ValueError("revision must be a positive integer")
    kind = "issued" if retrospective_as_of is None else "retrospective"
    holdings, _ = load_holdings(root)
    prices = load_prices(root, holdings)
    prices = prices.loc[prices.date.le(cutoff)].copy()
    prediction = experiment(holdings, prices, cutoff, min_train, max_age_days)
    data_hash = sha256(prices.to_csv(index=False).encode("utf-8") + holdings[["item_id", "category", "item_name"]].to_csv(index=False).encode("utf-8")).hexdigest()
    files = ("forecast_archive.py", "prediction.py", "global_analysis.py", "portfolio_data.py", "analyze_drop_cases.py")
    code_hash = sha256(b"".join((Path(__file__).parent / name).read_bytes() for name in files)).hexdigest()
    software = {name: importlib.metadata.version(name) for name in ("numpy", "pandas", "scikit-learn")}
    directory = root / "data/processed/forecast_archive"
    saved = []
    for row in prediction["future"].itertuples(index=False):
        if kind == "issued" and emitted > month_close(row.target_date):
            continue
        base_date = prediction["diagnostic"]["base_date"]
        selected = holdings if row.category == "global" else holdings.loc[holdings.category.eq(row.category)]
        base = prices.loc[prices.date.eq(base_date) & ~prices.date_estimated & prices.unit_price.notna()]
        base = base.drop_duplicates("item_id", keep="last").set_index("item_id").unit_price
        basket = [dict(item_id=r.item_id, category=r.category, item_name=r.item_name,
                       base_price=float(base[r.item_id]), weight=1 / len(selected))
                  for r in selected.sort_values("item_id").itertuples(index=False)]
        record = dict(schema=SCHEMA, kind=kind, category=row.category, revision=revision,
                      emitted_at=emitted.isoformat(), origin=row.origin.isoformat(), target_date=row.target_date.isoformat(),
                      horizon_months=1, base_date=base_date.isoformat(), basket=basket,
                      parameters=dict(min_train=min_train, max_age_days=max_age_days,
                                      information_cutoff=cutoff.isoformat(),
                                      model="StandardScaler+Ridge(alpha=1,solver=svd)",
                                      weighting="equal_item", close="calendar_month_end_local"),
                      code_hash=code_hash, data_hash=data_hash, software=software,
                      training_pairs=int(row.training_pairs), training_end=None if pd.isna(row.training_end) else row.training_end.isoformat(),
                      predictions={m: None if pd.isna(getattr(row, m)) else float(getattr(row, m)) for m in METHODS})
        record["archive_id"] = archive_key(record)
        record["payload_hash"] = digest(record)
        saved.append(save_record(record, directory))
    return saved


def evaluate(directory, prices, as_of, *, target_start=None, target_end=None):
    """Read archives; compare all methods on identical realized targets per sample."""
    cutoff = stamp(as_of)
    first = stamp(target_start) if target_start is not None else None
    last_target = stamp(target_end) if target_end is not None else None
    if first is not None and last_target is not None and first > last_target:
        raise ValueError("Target period is reversed")
    prices = validate_prices(prices)
    prices = prices.loc[~prices.date_estimated & prices.unit_price.notna() & prices.date.le(cutoff)]
    prices = prices.sort_values("date", kind="stable").drop_duplicates(["item_id", "date"], keep="last")
    rows = []
    for record in records(directory):
        target = stamp(record["target_date"])
        if (first is not None and target < first) or (last_target is not None and target > last_target):
            continue
        close = month_close(record["target_date"])
        status, reason, actual = "pending", "target_month_not_closed", float("nan")
        if stamp(record["emitted_at"]) > cutoff:
            reason = "not_emitted_at_evaluation_cutoff"
        elif close < cutoff:
            values = []
            for item in record["basket"]:
                eligible = prices.loc[prices.item_id.eq(item["item_id"]) & prices.date.le(close)]
                if eligible.empty:
                    break
                last = eligible.iloc[-1]
                if (close - last.date).total_seconds() / 86400 > record["parameters"]["max_age_days"]:
                    break
                values.append(last.unit_price / item["base_price"] * 100 * item["weight"])
            if len(values) == len(record["basket"]):
                status, reason, actual = "evaluated", "", float(sum(values))
            else:
                status, reason = "unavailable", "missing_or_stale_target_price"
        row = dict(archive_id=record["archive_id"], kind=record["kind"], category=record["category"],
                   revision=record["revision"], origin=record["origin"], target_date=record["target_date"],
                   emitted_at=record["emitted_at"], basket_hash=digest(dict(base_date=record["base_date"], basket=record["basket"])),
                   code_hash=record["code_hash"], status=status, reason=reason, actual=actual,
                   settings_hash=digest(dict(parameters=settings(record), software=record["software"])),
                   **record["predictions"])
        rows.append(row)
    columns = ["archive_id", "kind", "category", "revision", "origin", "target_date", "emitted_at", "basket_hash", "code_hash", "settings_hash", "status", "reason", "actual", *METHODS]
    details = pd.DataFrame(rows, columns=columns)
    metrics = []
    # Revisions/baskets/software versions are explicit groups, not pooled duplicates.
    grouping = ["kind", "category", "revision", "basket_hash", "code_hash", "settings_hash"]
    for keys, group in details.loc[details.status.eq("evaluated")].groupby(grouping):
        for sample, methods in (("baseline_common", METHODS[:2]), ("model_common", METHODS)):
            common = group.dropna(subset=list(methods))
            if common.empty:
                continue
            for method in methods:
                errors = common[method] - common.actual
                metrics.append(dict(zip(grouping, keys),
                                    sample=sample, method=method, windows=len(common),
                                    first_target=common.target_date.min(), last_target=common.target_date.max(),
                                    MAE=float(errors.abs().mean()), RMSE=float(np.sqrt(np.mean(errors ** 2)))))
    return details, pd.DataFrame(metrics, columns=[*grouping, "sample", "method", "windows", "first_target", "last_target", "MAE", "RMSE"])


def load_archive_prices(root=ROOT):
    """Keep removed others-item identities available to legacy price loading."""
    root = Path(root)
    holdings, _ = load_holdings(root)
    archived = records(root / "data/processed/forecast_archive")
    frozen = pd.DataFrame([dict(item_id=b["item_id"], category=b["category"], item_name=b["item_name"], quantity=0)
                           for r in archived for b in r["basket"]], columns=holdings.columns)
    registry = pd.concat([holdings, frozen], ignore_index=True).drop_duplicates("item_id")
    return load_prices(root, registry)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["issue", "evaluate"])
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--revision", type=int, default=1)
    parser.add_argument("--retrospective-as-of", help="Explicit simulation cutoff; never labeled a real issue")
    parser.add_argument("--min-train", type=int, default=12)
    parser.add_argument("--max-age-days", type=float, default=45)
    parser.add_argument("--target-start", help="Evaluation target-period start")
    parser.add_argument("--target-end", help="Evaluation target-period end")
    args = parser.parse_args(argv)
    if args.command == "issue":
        saved = issue(args.root, revision=args.revision, retrospective_as_of=args.retrospective_as_of,
                      min_train=args.min_train, max_age_days=args.max_age_days)
        print(f"Archived {len(saved)} category forecasts; no files are created without sufficient recent data.")
    else:
        details, metrics = evaluate(args.root / "data/processed/forecast_archive", load_archive_prices(args.root), pd.Timestamp.now(),
                                    target_start=args.target_start, target_end=args.target_end)
        print(details.to_string(index=False, na_rep="N/A"))
        print(metrics.to_string(index=False, na_rep="N/A"))


if __name__ == "__main__":
    main()
