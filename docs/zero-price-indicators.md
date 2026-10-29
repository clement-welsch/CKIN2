# Zero-price indicators

Tracking: #9. The former `analysis.ipynb` is now `notebook/cases_book.ipynb`.

Zero is a valid observed price and contributes zero to inventory valuation.
It is not a missing observation. Relative indicators need a nonzero denominator:

- A case whose first price is zero has no micro base-100 index or change since
  first observation, even if later prices become positive.
- If any case has a zero price at the first common date, the entire fixed-cohort
  macro index is unavailable. The notebook does not silently drop that case or
  select a later base date.
- Drawdown is unavailable when the historical peak is zero; observed range is
  unavailable when the minimum is zero.
- Snapshot percentage changes are unavailable after a zero total, as well as
  across incomplete valuations. A positive value falling to zero is -100%.

Unavailable values remain NaN in tables, with explanatory notebook messages.
Rankings exclude unavailable changes. Absolute prices and valuations are kept.

Validation: 40 synthetic tests passed on CPython 3.14.6, including all-zero
histories, zero-to-positive and positive-to-zero transitions. No personal CSVs
were read or modified and no Steam request was made.
