import requests
import pandas as pd

url = "https://steamcommunity.com/market/priceoverview/"

#inventory = pd.read_csv("../data/processed/drop_cases_inventory.csv")
#price_history = pd.read_csv("../data/processed/drop_cases_prices.csv")

appid = 730
currency = 3
market_hash_name = "Dreams & Nightmares"
market_hash_name += " Case"
market_hash_name = str.replace(market_hash_name, " ", "%20")
market_hash_name = str.replace(market_hash_name, "&", "%26")
print(market_hash_name)
print("https://steamcommunity.com/market/listings/730/Dreams%20%26%20Nightmares%20Case")
url = f"https://steamcommunity.com/market/listings/{appid}/{market_hash_name}"
print(url)
cookie = {'steamLogin': '686MadeInFrance686'}    
data = requests.get(url, cookies=cookie)
print(data)