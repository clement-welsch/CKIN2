# Offline creator-signal research (#40)

This is an experimental **local corpus** workflow, not an automated YouTube
scraper or a demonstrated forecasting improvement. The five requested creators
are listed in `config/community.example.json` as unverified. No channel ID, URL,
partnership or opinion is invented. Verify exact channel identities before
adding videos. The first real authorized corpus and its annotation review remain
to be supplied; no live collection is performed.

Source access: YouTube's official
[captions.download](https://developers.google.com/youtube/v3/docs/captions/download)
requires permission to edit the video. It does **not** authorize downloading
arbitrary creators' captions. Import TXT/SRT/VTT obtained through an authorized
source, record that method, and validate it manually on a small corpus before
considering automation. Human/automatic transcript origin is mandatory.

## Local files (all ignored)

Copy the example to `data/community/corpus.json`. A verified channel adds
`channel_id` (UC + 22 characters), canonical channel `url`, `verified_at`, and
`verified: true`. Video entries require `video_id` (11 characters), `channel_id`,
canonical watch `url`, `language`, `published_at`, `collected_at`, and `status`
(`available`, `missing_transcript`, `unavailable`). Available videos also require
`transcript_path` relative to the corpus directory, `transcript_origin`
(`human`/`automatic`), and `acquisition_note`. `content_group` groups known
reuploads/commentary using the same underlying source. Exact transcript copies
are grouped automatically; near-duplicate/reaction detection requires review.
Timestamps are local and timezone-naive, consistent with CKIN2's price contracts.

`data/community/aliases.json` contains reviewed records:

```json
[{"alias":"Example Case","item_ids":["stable catalog item ID"],"kind":"exact"}]
```

`exact` requires one candidate; `family`/`ambiguous` may identify several. Match
scores (1 or 0.5) express rule specificity, **not calibrated probabilities**.
Unmatched text is not evidence that no item was discussed. Supply aliases for
languages/spellings present in the corpus; no multilingual semantic model is
claimed. The reviewed catalog may contain non-owned objects from #39.

`extract()` returns signal IDs, short evidence excerpts, video/time links,
availability dates, candidates, extraction version and alias hash. SRT/VTT retain
times; TXT has no fabricated offset. Transcript content is never executed,
interpolated into commands or treated as model instructions. No LLM or external
model call is used by this version. Direction/horizon/arguments are deliberately
unknown until annotated, rather than guessed by keyword sentiment.

`annotations.json` maps a signal ID to `annotated_at`, `direction`
(`up`, `down`, `neutral`, `unknown`), optional `horizon`, `arguments` (creator
claims), `verified_facts` (separately checked), and `sponsorship` (only if
declared). Corrections refer to stable extraction IDs; stale IDs fail loudly.
Annotations become usable only at their annotation date, preventing hindsight
labels entering earlier forecasts. Audit a small sample before expanding it.

## Research and validation

Open `notebook/community_book.ipynb`; it reads local files and does not save
transcripts, price CSVs or issued forecasts. Without a corpus it shows an explicit
diagnostic. Raw full transcripts never enter tracked notebook outputs.

`features()` counts attention and independent content groups in the trailing 30
days, creator diversity, signed annotated opinions and disagreement. Ambiguous
and family matches are excluded from item features. Publication, collection and
annotation must all precede the forecast origin. Repeated copies do not become
independent creators. No current view-count feature is used.

`compare()` evaluates next-month per-item prices using observed, non-estimated
EUR prices from #39, a bounded 45-day backward match, and monthly walk-forward
origins. It compares persistence, simple trend, standardized Ridge on price
features, and the same Ridge plus community features. Models fit only past
training pairs; all four metrics use the same evaluated dates/items. Report MAE,
RMSE and sample counts, including zero targets. Fewer than 12 prior usable pairs
leave models/metrics unavailable. No arbitrary confidence interval is produced.
Inspect the backtest's past price movement alongside signals to distinguish
reaction from anticipation; correlation cannot establish causation. Original
data availability and curated-universe selection remain research limitations.

These are retrospective experiments, not real issued forecasts. #36 archives
remain separate and immutable; promotion of a community model into issued
forecasts requires a reviewed result and a new archive model/schema version.
No transactions are executed. Acceptance still requires a real annotated corpus,
verified channels, source-access check and an empirical prices-only comparison.

## Reviewed extraction sample

Optional ignored `data/community/evaluation.json` contains manually reviewed
passages. This measures mention extraction, separately from forecasting quality:

```json
{"schema":1,"passages":[{"video_id":"aaaaaaaaaaa","start_seconds":12.5,
 "reviewed_at":"2026-11-09","expected":[{"item_id":"known catalog ID","match_kind":"exact"}]}]}
```

Use `start_seconds: null` for a TXT passage and `expected: []` only when a human
reviewed that passage and confirmed no catalog mention. Include missed mentions
in expected labels; do not label only extracted positives. A passage is keyed by
video and offset; subtitle cues sharing an offset are reviewed together. Labels
are `(item_id, match_kind)` sets, with exact/family/ambiguous kept distinct.
Duplicate predictions do not inflate true positives. Unreviewed passages are
excluded, not assumed negative. Duplicate reviews or unknown catalog labels fail.

`research(..., as_of=...)` returns optional `evaluation` and the Research dashboard
shows its micro precision, recall, F1, TP/FP/FN and reviewed sample size. Reviews
after the cutoff are deferred. Zero denominators remain unavailable rather than
perfect. Sample hash, extractor and alias revisions identify the experiment.
Scores describe the whole reviewed sample through the selected end date, not
object-filtered coverage. They neither calibrate matching specificity nor prove
predictive value. No real annotated sample or measured quality is bundled;
the tests use only synthetic examples. #40's real-corpus validation stays open.
