#!/usr/bin/env python3
import json
import os
import sys
import time
import urllib.request
import urllib.error

API_BASE = "https://www.misdekor.cz/request.php"

OUTPUT_DIR = "output"
ORDERS_ALL = os.path.join(OUTPUT_DIR, "orders.json")
ORDERS_NEW = os.path.join(OUTPUT_DIR, "new_orders.json")

STATE_FILE = "state.json"

# Síťové limity (aby se to nikdy netočilo donekonečna)
TIMEOUT_SEC = 25
MAX_ATTEMPTS = 5
BACKOFF_BASE = 2


def log(msg: str):
    print(f"[fetch_orders] {msg}", flush=True)


def load_state() -> dict:
    """Načte state.json nebo vrátí default."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                return d
        except Exception as e:
            log(f"WARNING: state.json invalid: {e}")

    return {"last_id_order": 0}


def save_state(state: dict):
    """Uloží state.json."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def build_url(password: str) -> str:
    """Sestaví API URL."""
    return f"{API_BASE}?action=GetOrders&version=v2.0&password={password}"


def fetch_json(url: str):
    """Stáhne JSON s retry + timeout."""
    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            log(f"HTTP GET attempt {attempt}/{MAX_ATTEMPTS}")

            req = urllib.request.Request(
                url,
                headers={"User-Agent": "misdekor-gha"},
            )

            with urllib.request.urlopen(req, timeout=TIMEOUT_SEC) as resp:
                raw = resp.read()

            text = raw.decode("utf-8", errors="replace").strip()
            return json.loads(text)

        except Exception as e:
            last_error = e
            wait = BACKOFF_BASE * (2 ** (attempt - 1))
            log(f"ERROR: {type(e).__name__}: {e}")
            log(f"Retry in {wait}s...")
            time.sleep(wait)

    raise RuntimeError(f"Failed after {MAX_ATTEMPTS} attempts: {last_error}")


def normalize_orders(raw) -> list[dict]:
    """
    Normalizuje odpověď API na list[dict].
    Podporuje:
      - list[dict]
      - dict wrapper: {"orders":[...]}
    """
    data = raw

    if isinstance(data, dict):
        for key in ("orders", "data", "items", "result"):
            if key in data and isinstance(data[key], list):
                data = data[key]
                break

    if not isinstance(data, list):
        raise ValueError(f"Unexpected API structure: {type(raw)}")

    cleaned = []
    for o in data:
        if isinstance(o, dict):
            cleaned.append(o)

    return cleaned


def get_order_id(order: dict) -> int:
    """Vrátí id_order jako int."""
    val = order.get("id_order") or order.get("id") or 0
    try:
        return int(val)
    except Exception:
        return 0


def main():
    password = os.environ.get("ESHOP_API_PASSWORD", "").strip()
    if not password:
        log("ERROR: Missing ESHOP_API_PASSWORD secret")
        sys.exit(1)

    mode = os.environ.get("MODE", "live").strip().lower()
    if mode not in ("live", "test"):
        mode = "live"

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    url = build_url(password)

    log(f"Mode = {mode}")
    log("Fetching orders from API...")

    raw = fetch_json(url)
    orders = normalize_orders(raw)

    log(f"Fetched total orders: {len(orders)}")

    # Ulož všechny objednávky
    with open(ORDERS_ALL, "w", encoding="utf-8") as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)

    state = load_state()
    last_id = int(state.get("last_id_order", 0))

    # TEST režim: vždy exportuj všechny objednávky jako nové
    if mode == "test":
        with open(ORDERS_NEW, "w", encoding="utf-8") as f:
            json.dump(orders, f, ensure_ascii=False, indent=2)

        log("TEST MODE: new_orders.json = all orders")
        log("State not updated.")
        return

    # LIVE režim: jen nové objednávky
    new_orders = [o for o in orders if get_order_id(o) > last_id]
    new_orders = sorted(new_orders, key=get_order_id)

    with open(ORDERS_NEW, "w", encoding="utf-8") as f:
        json.dump(new_orders, f, ensure_ascii=False, indent=2)

    log(f"New orders since last_id_order={last_id}: {len(new_orders)}")

    # Update state.json
    if new_orders:
        max_id = max(get_order_id(o) for o in new_orders)
        state["last_id_order"] = max_id
        save_state(state)
        log(f"Updated state.json last_id_order={max_id}")
    else:
        log("No new orders, state unchanged.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"FATAL ERROR: {type(e).__name__}: {e}")
        sys.exit(1)
