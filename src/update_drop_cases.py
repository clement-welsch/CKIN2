import argparse
from datetime import date
from enum import Enum
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urlencode

import pandas as pd

STEAM_REQUEST_DELAY_SECONDS = 2
PROJECT_ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = PROJECT_ROOT / "data" / "processed" / "drop_cases_inventory.csv"
PRICE_HISTORY_PATH = PROJECT_ROOT / "data" / "processed" / "drop_cases_prices.csv"


class Environment(Enum):
    HOME = "home"
    SCHOOL = "school"

def connect_to_steam(name_case):
    # Terminals are listed without the "Case" suffix on Steam Market.
    market_hash_name = name_case if name_case.endswith(" Terminal") else f"{name_case} Case"
    params = urlencode({
        "appid": 730,
        "currency": 3,
        "market_hash_name": market_hash_name,
    })
    url = f"https://steamcommunity.com/market/priceoverview/?{params}"

    try:
        response = subprocess.run(
            [
                "curl.exe",
                "--silent",
                "--show-error",
                "--max-time",
                "10",
                "--write-out",
                "\n%{http_code}",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=12,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        print(f"Échec de la requête Steam pour {name_case} : {error}")
        return None

    if response.returncode != 0:
        print(f"Échec de curl pour {name_case} : {response.stderr.strip()}")
        return None

    body, _, status_text = response.stdout.rpartition("\n")
    status_code = int(status_text) if status_text.isdigit() else 0
    print("Status :", status_code)
    print("URL :", url)

    if status_code == 429:
        print("Steam rate limit atteint.")
        return None
    if status_code < 200 or status_code >= 300:
        print(f"Réponse HTTP inattendue pour {name_case} : {status_code}")
        return None

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        print(f"Réponse JSON invalide de Steam pour {name_case}.")
        return None

    lowest_price = data.get("lowest_price")
    if lowest_price is None:
        print(f"Aucun prix Steam disponible pour {name_case}.")
        return None

    # Steam may format prices with either decimal or thousands separators.
    price_text = "".join(char for char in lowest_price if char.isdigit() or char in ".,")
    if not re.search(r"\d", price_text):
        return None
    if "." in price_text and "," in price_text:
        decimal_separator = "." if price_text.rfind(".") > price_text.rfind(",") else ","
        thousands_separator = "," if decimal_separator == "." else "."
        price_text = price_text.replace(thousands_separator, "").replace(decimal_separator, ".")
    elif "," in price_text:
        price_text = price_text.replace(",", ".") if len(price_text.rsplit(",", 1)[1]) == 2 else price_text.replace(",", "")
    elif "." in price_text and len(price_text.rsplit(".", 1)[1]) != 2:
        price_text = price_text.replace(".", "")
    return float(price_text)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Update drop-case prices using Steam at home or the last saved price at school."
    )
    parser.add_argument(
        "environment",
        choices=[environment.value for environment in Environment],
        help="Execution location: home (Steam API) or school (reuse last known price).",
    )
    return parser.parse_args()


def main(environment):
    if environment is Environment.SCHOOL:
        print(
            "Mode école : les derniers prix enregistrés seront réutilisés "
            "pour l'évaluation, sans créer de nouveaux relevés."
        )
        return

    inventory = pd.read_csv(INVENTORY_PATH)
    list_cases = inventory["case_name"].dropna().unique()
    print(list_cases)
    new_rows = []
    for index, case in enumerate(list_cases):
        price = connect_to_steam(case)
        if index < len(list_cases) - 1:
            time.sleep(STEAM_REQUEST_DELAY_SECONDS)
        if price is None:
            continue
        new_row = {
            "date": date.today(),
            "case_name": case,
            "unit_price": price
        }
        new_rows.append(new_row)

    if new_rows:
        new_prices = pd.DataFrame(new_rows)
        price_history_path = PRICE_HISTORY_PATH
        if price_history_path.exists() and price_history_path.stat().st_size:
            with price_history_path.open("rb+") as price_file:
                price_file.seek(-1, 2)
                if price_file.read(1) not in (b"\n", b"\r"):
                    price_file.write(b"\n")
        new_prices.to_csv(
            price_history_path,
            mode="a",
            header=False,
            index=False
        )

if __name__ == "__main__":
    args = parse_args()
    main(Environment(args.environment))
