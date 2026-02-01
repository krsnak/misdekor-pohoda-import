import os
import urllib.request

BASE_URL = "https://www.misdekor.cz/request.php?action=GetOrders&version=v2.0&password="

def main() -> None:
    password = os.environ.get("ESHOP_API_PASSWORD")
    if not password:
        raise SystemExit("Missing env var ESHOP_API_PASSWORD")

    url = BASE_URL + password

    with urllib.request.urlopen(url, timeout=30) as resp:
        data = resp.read()

    os.makedirs("output", exist_ok=True)
    with open("output/orders.json", "wb") as f:
        f.write(data)

    print("Saved output/orders.json")

if __name__ == "__main__":
    main()
