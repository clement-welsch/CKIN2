import pandas as pd
import requests
from pathlib import Path

#ENVIRONMENT = "home"
ENVIRONMENT = "school"

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

def get_price_for_case(case_name):
    if ENVIRONMENT == "home":
        return connect_to_steam(case_name)
    else:
        df=pd.read_csv("./data/processed/drop_cases_prices.csv")
        price = df[df["case_name"] == case_name].tail(1)["unit_price"].iloc[0]
        print(price)
        return price

new_price = get_price_for_case("Dreams & Nightmares")
print(new_price)