"""Offline analysis of one sanitized history capture; never contact Steam."""

import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, unquote, urlsplit


def history_time(value):
    """Parse the explicit UTC-offset fixture contract, independently of locale."""
    match = re.fullmatch(r'([A-Z][a-z]{2}) (\d{1,2}) (\d{4}) (\d{2}): ([+-]\d{1,2})', str(value))
    if not match:
        raise ValueError('Unsupported history timestamp; retain raw capture for review')
    month, day, year, hour, offset = match.groups()
    months = 'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split()
    try:
        return datetime(int(year), months.index(month)+1, int(day), int(hour),
                        tzinfo=timezone(timedelta(hours=int(offset)))).astimezone(timezone.utc)
    except (ValueError, OverflowError) as error:
        raise ValueError('Invalid history timestamp') from error


def analyze_capture(capture):
    """Validate declared identity/provenance, not live access or data-use rights.

    This intentionally narrow fixture format is a hypothesis to check at home,
    not a claim that Steam guarantees this internal response schema.
    """
    if not isinstance(capture, dict) or type(capture.get('schema')) is not int or capture.get('schema') != 1:
        raise ValueError('Expected capture schema 1')
    name = capture.get('market_hash_name')
    if not isinstance(name, str) or not name.strip() or name != name.strip():
        raise ValueError('Exact market_hash_name required')
    urls = []
    for field in ('listing_url', 'response_url'):
        value = capture.get(field)
        if not isinstance(value, str) or not value or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError('Expected a nonempty URL string without whitespace or control characters')
        try:
            urls.append(urlsplit(value))
        except ValueError as error:
            raise ValueError('Invalid capture URL') from error
    listing, response_url = urls
    if (listing.scheme != 'https' or listing.netloc != 'steamcommunity.com' or listing.query or listing.fragment
            or unquote(listing.path) != '/market/listings/730/' + name):
        raise ValueError('Listing does not match the exact declared variant')
    if response_url.scheme != 'https' or response_url.netloc != 'steamcommunity.com' or response_url.path != '/market/pricehistory/' or response_url.fragment:
        raise ValueError('Expected exact history endpoint URL without credentials')
    query = parse_qs(response_url.query, keep_blank_values=True)
    if set(query) != {'appid', 'currency', 'market_hash_name'} or query['appid'] != ['730'] or query['market_hash_name'] != [name]:
        raise ValueError('Response identity mismatch or unexpected query parameters')
    currency = capture.get('currency')
    if currency != 'EUR' or query['currency'] != ['3']:
        raise ValueError('Study currently accepts declared EUR/currency=3 only; verify this mapping live')
    try:
        retrieved = datetime.fromisoformat(capture['retrieved_at'])
        if retrieved.tzinfo is None:
            raise ValueError('Capture timestamp needs an explicit timezone')
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError('Invalid retrieved_at timestamp') from error
    payload = capture.get('response')
    if not isinstance(payload, dict):
        raise ValueError('Unsuccessful or unsupported history response')
    success = payload.get('success')
    if not (success is True or type(success) is int and success == 1) or not isinstance(payload.get('prices'), list):
        raise ValueError('Unsuccessful or unsupported history response')
    rows = []
    seen = set()
    for entry in payload['prices']:
        if not isinstance(entry, list) or len(entry) != 3:
            raise ValueError('Expected timestamp, price and volume triples')
        date = history_time(entry[0])
        if date > retrieved or date in seen:
            raise ValueError('Future or duplicate history timestamp')
        seen.add(date)
        try:
            if isinstance(entry[1], bool):
                raise ValueError('Boolean price')
            price = Decimal(str(entry[1]))
            if not price.is_finite() or price < 0:
                raise ValueError('Invalid price')
        except (InvalidOperation, ValueError) as error:
            raise ValueError('Expected finite nonnegative numeric price') from error
        volume_text = str(entry[2])
        if not re.fullmatch(r'(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)', volume_text):
            raise ValueError('Unsupported volume format')
        rows.append(dict(timestamp_utc=date.isoformat(), price=str(price), volume=int(volume_text.replace(',', '')),
                         currency=currency, market_hash_name=name))
    rows.sort(key=lambda r: r['timestamp_utc'])
    dates = [datetime.fromisoformat(r['timestamp_utc']) for r in rows]
    steps = [(b-a).total_seconds()/3600 for a, b in zip(dates, dates[1:])]
    return dict(status='offline_sample_valid' if rows else 'empty_sample', live_verdict='pending',
                market_hash_name=name, currency=currency, retrieved_at=retrieved.isoformat(),
                points=len(rows), first_utc=rows[0]['timestamp_utc'] if rows else None,
                last_utc=rows[-1]['timestamp_utc'] if rows else None,
                observed_interval_hours=sorted(set(steps)), volume_total=sum(r['volume'] for r in rows),
                measure='unverified_history_price; validate median sales versus listing minimum against graph',
                authentication='not_tested', access_and_reuse='not_reviewed',
                limitations=['Synthetic/local capture validation is not a live go decision.',
                             'Intervals describe returned observations, not guaranteed bucket duration.',
                             'No interpolation, no-sales inference, or portfolio quantity reconstruction.'], rows=rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('environment', choices=['school'], help='Offline study only; live validation remains manual at home')
    parser.add_argument('--capture', type=Path, required=True, help='Sanitized JSON envelope; no cookies or credentials')
    args = parser.parse_args()
    try:
        result = analyze_capture(json.loads(args.capture.read_text(encoding='utf-8')))
    except (ValueError, OSError) as error:
        parser.exit(2, f'Capture rejected: {error}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
