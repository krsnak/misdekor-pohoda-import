import json
import os
import time
import urllib.request
from urllib.error import URLError
import socket

# --- Force IPv4 (GitHub Actions někdy selže na IPv6 trase) ---
socket.setdefaulttimeout(30)
_orig_getaddrinfo = socket.getaddrinfo

def _getaddrinfo_ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

socket.getaddrinfo = _getaddrinfo_ipv4
# ------------------------------------------------------------

BASE_URL = "https://www.misdekor.cz/request.php?action=GetOrders&version=v2.0&password="

STATE_PATH = "state.json"
OUT_ALL = "output/orders.json"
OUT_NEW = "output/new_orders.json"


def load_state() -> dict:
    if not os.path.exists(STATE_PATH):
        return {"last_id_order": 0}
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"last_id_order": 0}
        return data
    except Exception:
        return {"last_id_order": 0}


def save_state(state: dict) -> None:
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def fetch_with_retries(url: str, attempts: int = 5) -> bytes:
    last_err = None
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler())

    for attempt in range(1, attempts + 1):
        try:
            req = urllib.request.Request(url)
            with opener.open(req, timeout=30) as resp:
                return resp.read()
        except URLError as e:
            last_err = e
            print(f"Network error (attempt {attempt}/{attempts}): {e}")
            time.sleep(10 * attempt)

    raise SystemExit(f"Failed to fetch orders after retries: {last_err}")


def safe_int(value, default=None):
    try:
        return int(value)
    except Exception:
        return default


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

    orders = (data.get("params", {}) or {}).get("orderList", [])
    if not isinstance(orders, list):
        orders = []

    state = load_state()
    last_id = safe_int(state.get("last_id_order", 0), 0) or 0

    new_orders = []
    max_id = last_id

    for o in orders:
        oid = safe_int((o or {}).get("id_order"), None)
        if oid is None:
            continue

        if oid > last_id:
            new_orders.append(o)

        if oid > max_id:
            max_id = oid

    # FALLBACK: když nejsou nové, exportuj aspoň poslední 1 (nejvyšší id_order)
    if not new_orders and orders:
        def key_id(x):
            return safe_int((x or {}).get("id_order"), -1) or -1

        last_order = max(orders, key=key_id)
        if key_id(last_order) > 0:
            new_orders = [last_order]

    with open(OUT_NEW, "w", encoding="utf-8") as f:
        json.dump(new_orders, f, ensure_ascii=False, indent=2)

    state["last_id_order"] = max_id
    save_state(state)

    print(f"Saved {OUT_ALL}")
    print(f"Saved {OUT_NEW} (new: {len(new_orders)})")
    print(f"Updated state last_id_order: {last_id} -> {max_id}")

    if len(new_orders) == 1:
        oid = safe_int((new_orders[0] or {}).get("id_order"), -1)
        if oid != -1 and oid <= last_id:
            print("Info: No new orders; exported the latest one as fallback.")


if __name__ == "__main__":
    main()
