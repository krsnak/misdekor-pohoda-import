import json
import os
import time
import urllib.request
from urllib.error import URLError

BASE_URL = "https://www.misdekor.cz/request.php?action=GetOrders&version=v2.0&password="

STATE_PATH = "state.json"
OUT_ALL = "output/orders.json"
OUT_NEW = "output/new_orders.json"


def load_state() -> dict:
    if not os.path.exists(STATE_PATH):
        return {"last_id_order": 0}
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict) -> None:
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def fetch_with_retries(url: str, attempts: int = 5) -> bytes:
    raw = None
    last_err = None

    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                raw = resp.read()
            return raw
        except URLError as e:
            last_err = e
            print(f"Network error (attempt {attempt}/{attempts}): {e}")
            time.sleep(10 * attempt)  # 10s, 20s, 30s, ...

    raise SystemExit(f"Failed to fetch orders after retries: {last_err}")


def main() -> None:
    password = os.environ.get("ESHOP_API_PASSWORD")
    if not password:
        raise SystemExit("Missing env var ESHOP_API_PASSWORD")

    url = BASE_URL + password

    raw = fetch_with_retries(url)

    os.makedirs("output", exist_ok=True)
    with open(OUT_ALL, "wb") as f:
        f.write(raw)

    data = json.loads(raw.decode("utf-8", errors="replace"))

    # Tvoje API vrací objednávky v: params -> orderList
    orders = (data.get("params", {}) or {}).get("orderList", [])
    if not isinstance(orders, list):
        orders = []

    state = load_state()
    last_id = int(state.get("last_id_order", 0))

    new_orders = []
    max_id = last_id

    for o in orders:
        try:
            oid = int(o.get("id_order"))
        except Exception:
            continue

        if oid > last_id:
            new_orders.append(o)
            if oid > max_id:
                max_id = oid

    with open(OUT_NEW, "w", encoding="utf-8") as f:
        json.dump(new_orders, f, ensure_ascii=False, indent=2)

    # aktualizace stavu
    state["last_id_order"] = max_id
    save_state(state)

    print(f"Saved {OUT_ALL}")
    print(f"Saved {OUT_NEW} (new: {len(new_orders)})")
    print(f"Updated state last_id_order: {last_id} -> {max_id}")


if __name__ == "__main__":
    main()
