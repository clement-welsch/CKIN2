import requests

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

def get_price_for_case(name_case):
    connect_to_steam(name_case)
    return 0

get_price_for_case("Dreams & Nightmares")
