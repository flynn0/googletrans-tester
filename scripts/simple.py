import requests

PACKAGE = "googletrans-curl"
BASE_URL = f"https://pypistats.org/api/packages/{PACKAGE}"

response = requests.get(f"{BASE_URL}/recent", timeout=15)
response.raise_for_status()

stats = response.json()["data"]

print(f"Package: {PACKAGE}")
print(f"Downloads today:  {stats['last_day']:,}")
print(f"Downloads week:   {stats['last_week']:,}")
print(f"Downloads month:  {stats['last_month']:,}")

response = requests.get(f"{BASE_URL}/overall", timeout=15)
response.raise_for_status()

data = response.json()["data"]

for entry in data[-10:]:
    if entry["category"] == "without_mirrors":
        print(entry["date"], entry["downloads"])
