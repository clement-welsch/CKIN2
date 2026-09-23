import pandas as pd
import requests

# ENVIRONMENT = "home"
ENVIRONMENT = "school"

inventory = pd.read_csv("./data/processed/drop_cases_inventory.csv")
price_history = pd.read_csv("./data/processed/drop_cases_prices.csv")

price_history["date"] = pd.to_datetime(price_history["date"])

def connect_to_steam(name_case):
    appid = 730
    currency = 3
    market_hash_name = name_case
    market_hash_name += " Case"
    url = "https://steamcommunity.com/market/priceoverview/"

    params = {
    "appid": appid,
    "currency": currency,
    "market_hash_name": market_hash_name
    }

    response = requests.get(url, params=params, timeout=10)
    print(response.status_code)
    print(response.text)
    return response.json()

def get_price_for_case(case_name, price_history):
    if ENVIRONMENT == "home":
        return connect_to_steam(case_name)
    else:
        price = price_history[price_history["case_name"] == case_name].tail(1)["unit_price"].iloc[0]
        return price

list_cases = inventory["case_name"].unique()

for case_name in list_cases:
    new_price = get_price_for_case(case_name, price_history)
    print(case_name, new_price)