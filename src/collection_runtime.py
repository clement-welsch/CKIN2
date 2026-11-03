"""Local process lock and bounded, classified Steam retries."""

from contextlib import contextmanager
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from update_drop_cases import parse_market_price


class CollectionBusy(OSError):
    pass


@contextmanager
def collection_lock(root):
    """Kernel-held lock: a crashed/dead process cannot leave a stale lease.

    Keep the file in place: unlinking it would allow different locked inodes.
    """
    path = Path(root) / "data/runtime/collection.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise CollectionBusy("Another portfolio collection is running") from error
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def retry_after_seconds(value, now):
    if value is None:
        return 0.0
    try:
        return max(0.0, float(int(value)))
    except (ValueError, TypeError):
        try:
            stamp = parsedate_to_datetime(value)
            if stamp.tzinfo is None:
                return 0.0
            return max(0.0, (stamp - now).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return 0.0


class RetryingSteam:
    """Callable compatible with the shared collector; diagnostics omit names/URLs."""

    def __init__(self, attempts=3, base_delay=2, max_wait=120, *,
                 opener=urlopen, pause=time.sleep, clock=lambda: datetime.now(timezone.utc)):
        self.attempts, self.base_delay, self.max_wait = attempts, base_delay, max_wait
        self.opener, self.pause, self.clock = opener, pause, clock
        self.outcomes = []
        self.blocked_until = None

    def __call__(self, name):
        if self.blocked_until and self.clock() < self.blocked_until:
            self.outcomes.append(dict(kind="deferred", attempts=0, retry_at=self.blocked_until.isoformat()))
            return None
        url = "https://steamcommunity.com/market/priceoverview/?" + urlencode(
            {"appid": 730, "currency": 3, "market_hash_name": name})
        retry_at = None
        for attempt in range(1, self.attempts + 1):
            hint = None
            try:
                with self.opener(url, timeout=12) as response:
                    # Bound response memory and avoid persisting raw network payloads.
                    data = json.loads(response.read(1_000_001))
                price = parse_market_price(data)
                kind = "updated" if price is not None else "no_price"
                self.outcomes.append(dict(kind=kind, attempts=attempt))
                return price
            except HTTPError as error:
                hint = error.headers.get("Retry-After") if error.headers else None
                kind = "temporary" if error.code in (408, 429) or 500 <= error.code < 600 else "permanent_http"
                error.close()
            except (URLError, TimeoutError, ConnectionError, OSError):
                kind = "temporary"
            except (json.JSONDecodeError, UnicodeError, ValueError):
                kind = "invalid_response"
            if kind not in ("temporary", "invalid_response"):
                break
            wait = max(self.base_delay * 2 ** (attempt - 1), retry_after_seconds(hint, self.clock()))
            from datetime import timedelta
            retry_at = (self.clock() + timedelta(seconds=wait)).isoformat()
            # Never shorten Retry-After. Defer instead of blocking beyond the budget.
            if attempt == self.attempts or wait > self.max_wait:
                self.blocked_until = datetime.fromisoformat(retry_at)
                break
            self.pause(wait)
        self.outcomes.append(dict(kind=kind, attempts=attempt, retry_at=retry_at))
        return None
