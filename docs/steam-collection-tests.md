# Steam collection regression coverage

Tracking: #10. Tests mock `subprocess.run`; no request reaches Steam.

`test/test_steam_collection.py` covers URL encoding, terminal names, request
timeouts, decimal comma/dot, grouped thousands, spaces and nonbreaking spaces,
and a valid observed zero. It exercises HTTP 429 and other failures, curl exit
errors, missing curl, timeout exceptions, malformed JSON, unsuccessful responses,
missing prices and malformed price payloads.

The collector returns no observation for these failures. Signed prices, invalid
grouping, unexpected JSON types and nonfinite numeric results are rejected
rather than coerced into a plausible positive price. Existing history remains
byte-identical when collection fails. A mixed update appends only successful
observations, including valid zero prices, and preserves existing rows.

Validation: 43 synthetic tests passed on CPython 3.14.6. This verifies decoding
and persistence against fixtures, not live Steam availability or future format
changes. Existing retry and request-spacing behavior is unchanged.
