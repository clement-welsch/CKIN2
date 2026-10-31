"""One-month experimental index forecasts with expanding chronological evaluation."""

import numpy as np
import pandas as pd

from global_analysis import market_indices
from portfolio_data import CATEGORIES, validate_holdings, validate_prices

BACKTEST = ["category", "origin", "target_date", "actual", "persistence", "trend", "ridge", "training_pairs", "training_end"]


def monthly_series(indices, as_of, max_age_days=45):
    """Sample at completed month ends; carry only backward, with explicit age."""
    columns = ["date", "category", "index_100", "age_days"]
    if indices.empty:
        return pd.DataFrame(columns=columns)
    as_of = pd.Timestamp(as_of)
    # The current calendar month is never treated as completed, even on its last day.
    end = as_of.to_period("M").start_time - pd.Timedelta(days=1)
    rows = []
    for category, group in indices.groupby("category"):
        group = group.sort_values("date")
        for stamp in pd.date_range(group.date.min().normalize(), end, freq="ME"):
            close = stamp + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)
            eligible = group.loc[group.date.le(close)]
            if eligible.empty:
                continue
            last = eligible.iloc[-1]
            age = last.oldest_price_age_days + (close-last.date).total_seconds()/86400
            value = last.index_100 if age <= max_age_days else float("nan")
            rows.append(dict(date=stamp, category=category, index_100=value, age_days=age))
    return pd.DataFrame(rows, columns=columns)


def _features(values, index):
    if index < 2 or not np.isfinite(values[index-2:index+1]).all():
        return None
    return [values[index], values[index]-values[index-1], np.mean(values[index-2:index+1])]


def _fit(features, targets):
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    # Fresh preprocessing per origin. SVD is deterministic; no random splitting.
    model = make_pipeline(StandardScaler(), Ridge(alpha=1.0, solver="svd", random_state=0))
    return model.fit(np.asarray(features), np.asarray(targets))


def evaluate_series(series, min_train=12):
    """Return expanding backtests, future one-month forecasts and data diagnostics."""
    if isinstance(min_train, bool) or not isinstance(min_train, int) or min_train < 3:
        raise ValueError("min_train must be an integer >= 3")
    backtests, forecasts, audits = [], [], []
    for category, group in series.groupby("category"):
        group = group.sort_values("date").reset_index(drop=True)
        if group.date.duplicated().any():
            raise ValueError("Duplicate monthly target")
        if len(group) and not group.date.eq(group.date + pd.offsets.MonthEnd(0)).all():
            raise ValueError("Expected monthly end dates")
        # Reindex explicitly: never treat observations separated by a gap as adjacent months.
        grid = pd.date_range(group.date.min(), group.date.max(), freq="ME")
        group = group.set_index("date").reindex(grid).rename_axis("date").reset_index()
        values = group.index_100.to_numpy(dtype=float)
        if np.isinf(values).any() or (values[np.isfinite(values)] < 0).any():
            raise ValueError("Expected finite nonnegative indices or missing values")
        dates = group.date.tolist()
        features, targets, training_dates = [], [], []
        for index in range(len(values)):
            # Add only the pair whose target became observable at this origin.
            previous = _features(values, index-1) if index else None
            if previous is not None and np.isfinite(values[index]):
                features.append(previous)
                targets.append(values[index])
                training_dates.append(dates[index])
            if index < 1 or not np.isfinite(values[index-1:index+1]).all():
                continue
            origin = dates[index]
            target_date = origin + pd.offsets.MonthEnd(1)
            current = _features(values, index)
            ridge = float("nan")
            if current is not None and len(targets) >= min_train:
                ridge = max(0.0, float(_fit(features, targets).predict([current])[0]))
            row = dict(category=category, origin=origin, target_date=target_date,
                       persistence=values[index], trend=max(0.0, 2*values[index]-values[index-1]),
                       ridge=ridge, training_pairs=len(targets),
                       training_end=training_dates[-1] if training_dates else pd.NaT)
            if index+1 < len(values) and np.isfinite(values[index+1]):
                backtests.append(dict(**row, actual=values[index+1]))
            if index == len(values)-1:
                forecasts.append(row)
        tested = [r for r in backtests if r["category"] == category]
        model_tests = sum(pd.notna(r["ridge"]) for r in tested)
        audits.append(dict(category=category, first_date=dates[0] if dates else pd.NaT,
                           last_date=dates[-1] if dates else pd.NaT, calendar_months=len(values),
                           available_months=int(np.isfinite(values).sum()), missing_months=int((~np.isfinite(values)).sum()),
                           baseline_windows=len(tested), model_windows=model_tests, training_pairs=len(targets),
                           status="experimental_model" if model_tests else "insufficient_model_history",
                           required_training_pairs=min_train))
    return (pd.DataFrame(backtests, columns=BACKTEST),
            pd.DataFrame(forecasts, columns=[c for c in BACKTEST if c != "actual"]),
            pd.DataFrame(audits, columns=["category", "first_date", "last_date", "calendar_months", "available_months", "missing_months", "baseline_windows", "model_windows", "training_pairs", "status", "required_training_pairs"]))


def scores(backtests):
    """Compare methods on identical origins; RMSE/MAE support zero targets."""
    rows = []
    for category, group in backtests.groupby("category"):
        for sample, subset, methods in [("baseline_common", group, ["persistence", "trend"]),
                                        ("model_common", group.dropna(subset=["ridge"]), ["persistence", "trend", "ridge"])]:
            if subset.empty:
                continue
            for method in methods:
                errors = subset[method] - subset.actual
                rows.append(dict(category=category, sample=sample, method=method, windows=len(subset),
                                 first_target=subset.target_date.min(), last_target=subset.target_date.max(),
                                 MAE=float(errors.abs().mean()), RMSE=float(np.sqrt(np.mean(errors**2)))))
    return pd.DataFrame(rows, columns=["category", "sample", "method", "windows", "first_target", "last_target", "MAE", "RMSE"])


def experiment(holdings, prices, as_of, min_train=12, max_age_days=45):
    holdings, prices = validate_holdings(holdings), validate_prices(prices)
    as_of = pd.Timestamp(as_of)
    prices = prices.loc[prices.date.le(as_of)]
    indices, diagnostic = market_indices(holdings, prices, max_age_days)
    monthly = monthly_series(indices, as_of, max_age_days)
    backtests, future, audit = evaluate_series(monthly, min_train)
    missing = [c for c in [*CATEGORIES, "global"] if c not in set(audit.category)]
    if missing:
        absent = pd.DataFrame([dict(category=c, available_months=0, baseline_windows=0, model_windows=0,
                                    training_pairs=0, required_training_pairs=min_train,
                                    status=diagnostic.get("reason") or "No tracked cohort in this category") for c in missing])
        audit = pd.concat([audit, absent], ignore_index=True)
    return dict(monthly=monthly, backtests=backtests, future=future, audit=audit,
                scores=scores(backtests), diagnostic=diagnostic)
