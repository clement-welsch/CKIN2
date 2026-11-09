"""Offline, provenance-aware transcript research; transcripts are inert data."""

from hashlib import sha256
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd

from portfolio_data import HOLDINGS, ROOT, validate_prices
from market_universe import timestamp
from update_market_prices import validate_catalog

EXTRACTOR = "reviewed-aliases-v1"
SIGNALS = ["signal_id", "video_id", "channel_id", "content_group", "published_at", "collected_at",
           "available_at", "item_id", "match_kind", "confidence", "start_seconds", "url", "excerpt",
           "direction", "horizon", "arguments", "verified_facts", "sponsorship", "extractor", "alias_hash",
           "language", "transcript_origin", "acquisition_note"]


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def seconds(value):
    parts = value.replace(",", ".").split(":")
    if len(parts) not in (2, 3):
        raise ValueError("Expected MM:SS.mmm or HH:MM:SS.mmm")
    numbers = [float(p) for p in parts]
    if any(not np.isfinite(n) or n < 0 for n in numbers) or numbers[-1] >= 60 or (len(parts) == 3 and numbers[-2] >= 60):
        raise ValueError("Invalid subtitle timestamp")
    return sum(n * 60**i for i, n in enumerate(reversed(numbers)))


def transcript(text, suffix):
    """Keep exact segment times; TXT has no invented timestamp."""
    if suffix.lower() == ".txt":
        return [dict(start=None, end=None, text=text.strip())] if text.strip() else []
    if suffix.lower() not in (".srt", ".vtt"):
        raise ValueError("Only TXT/SRT/VTT imports are supported")
    rows = []
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n").lstrip("\ufeff")):
        lines = block.strip().splitlines()
        timing = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if timing is None:
            if block.strip() and not block.startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
                raise ValueError("Subtitle block has no timestamp")
            continue
        left, right = lines[timing].split("-->", 1)
        start, end = seconds(left.strip()), seconds(right.strip().split()[0])
        if end < start:
            raise ValueError("Subtitle end precedes start")
        content = " ".join(lines[timing+1:]).strip()
        if content:
            rows.append(dict(start=start, end=end, text=re.sub(r"<[^>]*>", "", content)))
    if any(a["start"] > b["start"] for a, b in zip(rows, rows[1:])):
        raise ValueError("Subtitle segments must be chronological")
    return rows


def validate_manifest(manifest):
    if manifest.get("schema") != 1 or not isinstance(manifest.get("channels"), list) or not isinstance(manifest.get("videos"), list):
        raise ValueError("Expected corpus schema 1, channels and videos")
    channels = {}
    for channel in manifest["channels"]:
        if not isinstance(channel.get("name"), str) or not channel["name"].strip() or type(channel.get("verified")) is not bool:
            raise ValueError("Invalid channel entry")
        if not channel["verified"]:
            continue
        channel_id = channel.get("channel_id")
        if not isinstance(channel_id, str) or not re.fullmatch(r"UC[A-Za-z0-9_-]{22}", channel_id) or channel_id in channels:
            raise ValueError("Expected unique verified YouTube channel IDs")
        if channel.get("url") != f"https://www.youtube.com/channel/{channel_id}":
            raise ValueError("Channel URL differs from verified ID")
        timestamp(channel["verified_at"])
        channels[channel_id] = channel
    seen = set()
    for video in sorted(manifest["videos"], key=lambda v: (v["published_at"], v["video_id"])):
        video_id = video.get("video_id")
        if not isinstance(video_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id) or video_id in seen:
            raise ValueError("Expected unique YouTube video IDs")
        seen.add(video_id)
        if video.get("channel_id") not in channels or video.get("url") != f"https://www.youtube.com/watch?v={video_id}":
            raise ValueError("Video requires a verified channel and exact URL")
        if timestamp(video["published_at"]) > timestamp(video["collected_at"]):
            raise ValueError("Video collection precedes publication")
        if timestamp(channels[video["channel_id"]]["verified_at"]) > timestamp(video["collected_at"]):
            raise ValueError("Channel verification follows collection")
        if not isinstance(video.get("language"), str) or not video["language"]:
            raise ValueError("Missing video language")
        if video.get("status") not in ("available", "unavailable", "missing_transcript"):
            raise ValueError("Invalid availability status")
        if video["status"] == "available":
            if video.get("transcript_origin") not in ("human", "automatic") or not video.get("acquisition_note"):
                raise ValueError("Transcript origin and authorized acquisition provenance required")
    return channels


def validate_aliases(aliases, catalog):
    validate_catalog(catalog, catalog.assign(quantity=0)[HOLDINGS])
    seen = set()
    for alias in aliases:
        name, ids, kind = alias.get("alias"), alias.get("item_ids"), alias.get("kind")
        if not isinstance(name, str) or not name.strip() or name != name.strip() or name.casefold() in seen:
            raise ValueError("Expected unique nonblank aliases")
        seen.add(name.casefold())
        if not isinstance(ids, list) or not ids or len(ids) != len(set(ids)) or not set(ids).issubset(catalog.item_id):
            raise ValueError("Alias requires known candidate identities")
        if kind not in ("exact", "family", "ambiguous") or (kind == "exact" and len(ids) != 1):
            raise ValueError("Invalid exact/family/ambiguous match")


def extract(manifest, aliases, catalog, corpus_directory, annotations=None):
    validate_manifest(manifest)
    validate_aliases(aliases, catalog)
    annotations = annotations or {}
    directory = Path(corpus_directory).resolve()
    rows, coverage = [], []
    alias_hash = digest(aliases)
    content_groups = {}
    for video in sorted(manifest["videos"], key=lambda v: (v["published_at"], v["video_id"])):
        if video["status"] != "available":
            coverage.append(dict(video_id=video["video_id"], status=video["status"], segments=0, signals=0))
            continue
        path = (directory / video["transcript_path"]).resolve()
        if not path.is_relative_to(directory):
            raise ValueError("Transcript must stay within corpus directory")
        if not path.exists():
            coverage.append(dict(video_id=video["video_id"], status="missing_transcript", segments=0, signals=0))
            continue
        segments = transcript(path.read_text(encoding="utf-8-sig"), path.suffix)
        fingerprint = digest(" ".join(s["text"].casefold() for s in segments))
        group = video.get("content_group") or fingerprint
        # Exact copies and explicitly declared syndication share a content group.
        group = content_groups.setdefault(fingerprint, group)
        count = 0
        for index, segment in enumerate(segments):
            for alias in aliases:
                if not re.search(r"(?<!\w)" + re.escape(alias["alias"]) + r"(?!\w)", segment["text"], re.IGNORECASE):
                    continue
                for item_id in alias["item_ids"]:
                    signal_id = digest([video["video_id"], fingerprint, index, alias["alias"], item_id, alias_hash, EXTRACTOR])
                    correction = annotations.get(signal_id)
                    available = timestamp(video["collected_at"])
                    direction, horizon, arguments, facts, sponsorship = "unknown", None, [], [], None
                    if correction:
                        if correction.get("direction") not in ("up", "down", "neutral", "unknown"):
                            raise ValueError("Invalid annotated direction")
                        available = max(available, timestamp(correction["annotated_at"]))
                        direction, horizon = correction["direction"], correction.get("horizon")
                        arguments, facts = correction.get("arguments", []), correction.get("verified_facts", [])
                        sponsorship = correction.get("sponsorship")
                        if not isinstance(arguments, list) or not isinstance(facts, list) or not all(isinstance(v, str) for v in [*arguments, *facts]):
                            raise ValueError("Annotations require string lists")
                    rows.append(dict(signal_id=signal_id, video_id=video["video_id"], channel_id=video["channel_id"],
                                     content_group=group, published_at=timestamp(video["published_at"]),
                                     collected_at=timestamp(video["collected_at"]), available_at=available, item_id=item_id,
                                     match_kind=alias["kind"], confidence=1.0 if alias["kind"] == "exact" else 0.5,
                                     start_seconds=segment["start"], url=video["url"] + (f"&t={int(segment['start'])}s" if segment["start"] is not None else ""),
                                     excerpt=segment["text"][:200], direction=direction, horizon=horizon, arguments=arguments,
                                     verified_facts=facts, sponsorship=sponsorship, extractor=EXTRACTOR, alias_hash=alias_hash,
                                     language=video["language"], transcript_origin=video["transcript_origin"], acquisition_note=video["acquisition_note"]))
                    count += 1
        coverage.append(dict(video_id=video["video_id"], status="imported", segments=len(segments), signals=count))
    unknown = set(annotations) - {r["signal_id"] for r in rows}
    if unknown:
        raise ValueError("Annotations refer to stale or unknown extraction IDs")
    return pd.DataFrame(rows, columns=SIGNALS), pd.DataFrame(coverage, columns=["video_id", "status", "segments", "signals"])


def features(signals, item_id, origin, lookback_days=30):
    origin = timestamp(origin)
    if type(lookback_days) is not int or lookback_days <= 0:
        raise ValueError("Positive lookback required")
    if signals.empty:
        return dict(attention=0, creators=0, net_direction=0, disagreement=0)
    selected = signals.loc[signals.item_id.eq(item_id) & signals.match_kind.eq("exact") &
                           signals.published_at.le(origin) & signals.collected_at.le(origin) &
                           signals.published_at.gt(origin-pd.Timedelta(days=lookback_days))]
    # Count original content groups once, even if repeated by another creator.
    selected = selected.sort_values(["published_at", "video_id", "signal_id"], kind="stable").drop_duplicates("content_group")
    directions = selected.direction.map({"up": 1, "down": -1, "neutral": 0, "unknown": 0})
    # A later annotation must not erase an earlier known mention or reveal its
    # future stance. Attention is available at collection, stance at annotation.
    directions = directions.where(selected.available_at.le(origin), 0)
    return dict(attention=len(selected), creators=selected.channel_id.nunique(), net_direction=int(directions.sum()),
                disagreement=int(directions.gt(0).any() and directions.lt(0).any()))


def compare(prices, signals, *, as_of, min_train=12, max_age_days=45):
    """Walk-forward next-month price forecast; compare identical origins/items."""
    prices = validate_prices(prices)
    cutoff = timestamp(as_of)
    if type(min_train) is not int or min_train < 3 or not np.isfinite(max_age_days) or max_age_days < 0:
        raise ValueError("Invalid training/freshness policy")
    prices = prices.loc[prices.date.le(cutoff) & ~prices.date_estimated & prices.unit_price.notna()]
    rows, audits = [], []
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    for item_id, group in prices.groupby("item_id"):
        group = group.sort_values("date", kind="stable").drop_duplicates("date", keep="last")
        dates = pd.date_range(group.date.min().normalize() + pd.offsets.MonthEnd(0), cutoff.normalize(), freq="ME")
        observed = []
        for date in dates:
            close = date + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)
            if close > cutoff:
                continue
            eligible = group.loc[group.date.le(close)]
            last = eligible.iloc[-1] if len(eligible) else None
            observed.append((date, last.unit_price if last is not None and (close-last.date).total_seconds()/86400 <= max_age_days else np.nan))
        training = []
        for index in range(1, len(observed)-1):
            date, value = observed[index]
            prior, actual = observed[index-1][1], observed[index+1][1]
            if not np.isfinite([prior, value, actual]).all():
                continue
            close = date + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)
            context = list(features(signals, item_id, close).values())
            price_x, full_x = [value, value-prior], [value, value-prior, *context]
            price_model = community_model = np.nan
            if len(training) >= min_train:
                target = [t[2] for t in training]
                def fit(values, current):
                    model = make_pipeline(StandardScaler(), Ridge(alpha=1.0))
                    return max(0.0, float(model.fit(values, target).predict([current])[0]))
                price_model = fit([t[0] for t in training], price_x)
                community_model = fit([t[1] for t in training], full_x)
            rows.append(dict(item_id=item_id, origin=date, target_date=observed[index+1][0], actual=actual,
                             persistence=value, trend=max(0, 2*value-prior), price_model=price_model,
                             community_model=community_model, training_pairs=len(training),
                             training_end=training[-1][3] if training else pd.NaT, **features(signals, item_id, close)))
            # This target is available at the next iteration's origin, never earlier.
            training.append((price_x, full_x, actual, observed[index+1][0]))
        audits.append(dict(item_id=item_id, monthly_points=len(observed), usable_points=sum(np.isfinite(v) for _, v in observed),
                           training_pairs=len(training), status="experimental" if len(training) > min_train else "insufficient_history"))
    results = pd.DataFrame(rows, columns=["item_id", "origin", "target_date", "actual", "persistence", "trend", "price_model", "community_model", "training_pairs", "training_end", "attention", "creators", "net_direction", "disagreement"])
    metrics = []
    for item_id, group in results.groupby("item_id"):
        common = group.dropna(subset=["price_model", "community_model"])
        for method in ("persistence", "trend", "price_model", "community_model"):
            if len(common):
                errors = common[method] - common.actual
                metrics.append(dict(item_id=item_id, method=method, windows=len(common), MAE=errors.abs().mean(), RMSE=np.sqrt((errors**2).mean())))
    return results, pd.DataFrame(metrics, columns=["item_id", "method", "windows", "MAE", "RMSE"]), pd.DataFrame(audits, columns=["item_id", "monthly_points", "usable_points", "training_pairs", "status"])


def research(root=ROOT, as_of=None):
    root = Path(root)
    directory = root / "data/community"
    manifest_path = directory / "corpus.json"
    if not manifest_path.exists():
        return dict(status="No local corpus. Channel identities and authorized transcript access remain unverified.",
                    channels=pd.DataFrame(), signals=pd.DataFrame(columns=SIGNALS), coverage=pd.DataFrame(), backtests=pd.DataFrame(), scores=pd.DataFrame(), audit=pd.DataFrame())
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    aliases = json.loads((directory / "aliases.json").read_text(encoding="utf-8"))
    catalog = pd.read_csv(root / "data/processed/market_catalog.csv")
    annotations_path = directory / "annotations.json"
    annotations = json.loads(annotations_path.read_text(encoding="utf-8")) if annotations_path.exists() else {}
    signals, coverage = extract(manifest, aliases, catalog, directory, annotations)
    videos = pd.DataFrame(manifest["videos"])
    if not videos.empty:
        coverage = coverage.merge(videos[["video_id", "channel_id", "url", "language", "published_at", "collected_at"]],
                                  on="video_id", validate="one_to_one")
    # Independent market universe observations include non-owned items.
    path = root / "data/market/observations.csv"
    from portfolio_data import PRICES
    prices = pd.read_csv(path) if path.exists() else pd.DataFrame(columns=PRICES)
    cutoff = pd.Timestamp.now() if as_of is None else timestamp(as_of)
    backtests, scores, audit = compare(prices, signals, as_of=cutoff)
    return dict(status="Offline experimental study; no causal or predictive benefit established.",
                channels=pd.DataFrame(manifest["channels"]), signals=signals, coverage=coverage,
                backtests=backtests, scores=scores, audit=audit)
