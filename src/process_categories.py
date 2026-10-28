"""Normalize local spreadsheet exports without changing existing case data."""

import argparse
import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INVENTORY_COLUMNS = ["item_name", "item_type", "quantity", "purchase_unit_price", "purchase_date"]
PRICE_COLUMNS = ["date", "item_name", "unit_price", "date_estimated", "source_file", "source_column"]


def number(value):
    """Preserve blanks; reject malformed and negative numeric cells."""
    if not value.strip():
        return ""
    try:
        result = Decimal(value.replace(",", "."))
    except InvalidOperation as error:
        raise ValueError(f"Invalid number: {value!r}") from error
    if not result.is_finite() or result < 0:
        raise ValueError(f"Invalid number: {value!r}")
    return str(result)


def parse_date(value):
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    return None


def observation_dates(header, start, *, paired=False, sticker_layout=False):
    """Interpolate undated market columns between known dates, never purchases."""
    columns = [2, *range(3, len(header), 2)] if sticker_layout else list(range(start, len(header), 2 if paired else 1))
    dates = {i: parse_date(header[i]) for i in columns}
    known = {i: value for i, value in dates.items() if value is not None}
    result = {}
    for i in columns:
        stamp = dates[i]
        estimated = stamp is None
        if stamp is None:
            before = [j for j in known if j < i]
            after = [j for j in known if j > i]
            if not before or not after:
                raise ValueError(f"Market column {i + 1} has no bounding dates")
            left, right = max(before), min(after)
            stamp = known[left] + (known[right] - known[left]) * ((i-left)/(right-left))
        result[i] = (stamp.date().isoformat(), estimated)
    return result


def convert(raw_dir):
    """Return inventories, prices and explicit source-data issues."""
    inventories = {name: [] for name in ("skins", "souvenirs", "others", "drop_cases")}
    prices = {name: [] for name in inventories}
    issues = []
    for filename in ("skins.csv", "souvenirs_cases.csv", "stickers.csv", "drop_cases.csv"):
        with (raw_dir / filename).open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))
        header = rows[0]
        paired = filename in ("souvenirs_cases.csv", "drop_cases.csv")
        start = 3 if filename == "souvenirs_cases.csv" else 2
        if filename == "skins.csv":
            start = 3  # Column 2 is the purchase price, with no purchase date.
        dates = observation_dates(header, start, paired=paired, sticker_layout=filename == "stickers.csv")
        tournament = ""
        for row_number, row in enumerate(rows[1:], 2):
            if len(row) != len(header):
                raise ValueError(f"{filename}:{row_number}: inconsistent column count")
            if filename == "souvenirs_cases.csv":
                if row[0].strip():
                    tournament = row[0].strip()
                if not row[1].strip():
                    continue  # Tournament heading or spreadsheet totals.
                if not tournament:
                    raise ValueError("Souvenir map without tournament")
                name, kind, category = f"{tournament} {row[1].strip()} Souvenir Package", "souvenir", "souvenirs"
                quantity = number(row[2])
            else:
                name = row[0].strip()
                if not name:
                    continue  # Spreadsheet totals.
                kind, category = "case", "drop_cases"
                if filename == "stickers.csv":
                    kind, category = "sticker", "others"
                elif filename == "skins.csv":
                    kind, category = "skin", "skins"
                    if name.startswith("Charm |"):
                        kind, category = "charm", "others"
                    elif name in ("Bio-Haz Specialist | SWAT", "Bloody Darryl The Strapped | The Professionals"):
                        kind, category = "agent", "others"
                quantity = number(row[1])
            if quantity and Decimal(quantity) % 1:
                raise ValueError(f"{filename}:{row_number}: quantity must be a whole number")
            purchase = number(row[2]) if filename == "skins.csv" else ""
            inventories[category].append(dict(zip(INVENTORY_COLUMNS, [name, kind, quantity, purchase, ""])))
            if not quantity:
                issues.append({"source_file": filename, "source_row": row_number, "item_name": name, "issue": "missing_quantity"})
            for column, (date, estimated) in dates.items():
                price = number(row[column])
                if price == "":
                    continue
                prices[category].append(dict(zip(PRICE_COLUMNS, [date, name, price, estimated, filename, column + 1])))
    return inventories, prices, issues


def write_csv(path, columns, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def preserve_acquisitions(path, generated):
    """Retain manual acquisition references without treating them as purchases."""
    acquisitions = []
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != PRICE_COLUMNS:
                raise ValueError(f"{path}: unexpected price CSV columns; file preserved")
            for row in reader:
                if row.get("source_column") != "0":
                    continue
                if None in row or any(value is None for value in row.values()):
                    raise ValueError(f"{path}: malformed acquisition row; file preserved")
                datetime.strptime(row["date"], "%Y-%m-%d")
                if not row["item_name"].strip():
                    raise ValueError(f"{path}: acquisition item name is missing")
                number(row["unit_price"])
                if row["date_estimated"] not in ("True", "False"):
                    raise ValueError(f"{path}: invalid date_estimated flag")
                acquisitions.append(row)
    # Keep both records on matching dates; the market observation follows the
    # acquisition reference so existing last-observation rules remain useful.
    return sorted([*acquisitions, *generated], key=lambda row: (
        row["item_name"], row["date"], int(row["source_column"])
    ))


def main(root=PROJECT_ROOT):
    inventories, prices, issues = convert(root / "data/raw")
    target = root / "data/processed"
    target.mkdir(parents=True, exist_ok=True)
    # Read and validate every existing price file before writing any exports.
    for category in ("skins", "souvenirs", "others"):
        prices[category] = preserve_acquisitions(target / f"{category}_prices.csv", prices[category])
    for category in ("skins", "souvenirs", "others"):
        write_csv(target / f"{category}_inventory.csv", INVENTORY_COLUMNS, inventories[category])
        write_csv(target / f"{category}_prices.csv", PRICE_COLUMNS, prices[category])
        print(f"{category}: {len(inventories[category])} items, {len(prices[category])} prices")
    # Existing case CSVs may contain newer private quantities and Steam prices.
    for suffix, columns, rows in (
        ("inventory", ["case_name", "quantity"], [{"case_name": r["item_name"], "quantity": r["quantity"]} for r in inventories["drop_cases"]]),
        ("prices", ["date", "case_name", "unit_price"], [{"date": r["date"], "case_name": r["item_name"], "unit_price": r["unit_price"]} for r in prices["drop_cases"]]),
    ):
        path = target / f"drop_cases_{suffix}.csv"
        if not path.exists():
            write_csv(path, columns, rows)
    write_csv(target / "category_import_issues.csv", ["source_file", "source_row", "item_name", "issue"], issues)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    main()
