"""Evaluate mention extraction on explicitly reviewed passages, never raw text."""

import math
import re

import pandas as pd

from community_signals import EXTRACTOR, digest
from market_universe import timestamp


def evaluate_extraction(signals, sample, catalog, as_of):
    """Micro precision/recall on reviewed (video, offset, item, match-kind) sets.

    An empty expected list is a reviewed negative. Unreviewed passages are
    excluded, never silently treated as negatives. Zero denominators stay null.
    """
    if not isinstance(sample, dict) or sample.get('schema') != 1 or not isinstance(sample.get('passages'), list):
        raise ValueError('Expected evaluation schema 1 and passages')
    cutoff = timestamp(as_of)
    known = set(catalog.item_id)
    reviewed, expected, seen = set(), set(), set()
    deferred = 0
    def position(video, offset):
        if not isinstance(video, str) or not re.fullmatch(r'[A-Za-z0-9_-]{11}', video):
            raise ValueError('Invalid reviewed video ID')
        if offset is not None and (isinstance(offset, bool) or not isinstance(offset, (int, float)) or not math.isfinite(offset) or offset < 0):
            raise ValueError('Expected nonnegative subtitle offset or null for TXT')
        return video, offset
    for passage in sample['passages']:
        if not isinstance(passage, dict) or not {'video_id', 'start_seconds', 'reviewed_at', 'expected'}.issubset(passage):
            raise ValueError('Incomplete reviewed passage')
        key = position(passage['video_id'], passage['start_seconds'])
        if key in seen:
            raise ValueError('Duplicate reviewed passage')
        seen.add(key)
        date = timestamp(passage['reviewed_at'])
        if pd.isna(date):
            raise ValueError('Missing review date')
        if not isinstance(passage['expected'], list):
            raise ValueError('Expected mention list; use [] for a reviewed negative')
        mentions = set()
        for mention in passage['expected']:
            if not isinstance(mention, dict) or mention.get('item_id') not in known or mention.get('match_kind') not in ('exact', 'family', 'ambiguous'):
                raise ValueError('Expected known item identity and match kind')
            identity = (*key, mention['item_id'], mention['match_kind'])
            if identity in mentions:
                raise ValueError('Duplicate expected mention')
            mentions.add(identity)
        if date > cutoff:
            deferred += 1
            continue
        reviewed.add(key)
        expected.update(mentions)
    predicted = set()
    eligible = signals.loc[signals.published_at.le(cutoff) & signals.collected_at.le(cutoff)] if not signals.empty else signals
    for row in eligible.itertuples():
        offset = None if pd.isna(row.start_seconds) else row.start_seconds
        key = position(row.video_id, offset)
        if key in reviewed:
            predicted.add((*key, row.item_id, row.match_kind))
    tp, fp, fn = len(predicted & expected), len(predicted - expected), len(expected - predicted)
    precision = tp / (tp+fp) if tp+fp else None
    recall = tp / (tp+fn) if tp+fn else None
    return dict(status='reviewed_sample' if reviewed else 'no_reviewed_sample',
                reviewed_passages=len(reviewed), deferred_passages=deferred, expected_mentions=len(expected),
                predicted_mentions=len(predicted), true_positives=tp, false_positives=fp, false_negatives=fn,
                precision=precision, recall=recall, f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
                extractor=EXTRACTOR, sample_hash=digest(sample),
                alias_hashes=sorted(eligible.alias_hash.dropna().unique().tolist()) if not eligible.empty else [],
                limitation='Reviewed sample only; specificity scores are not calibrated probabilities or evidence of predictive value.')
