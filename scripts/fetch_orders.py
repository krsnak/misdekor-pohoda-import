#!/usr/bin/env python3
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime

API_BASE = "https://www.misdekor.cz/request.php"
OUTPUT_DIR = "output"
ORDERS_ALL = os.path.join(OUTPUT_DIR, "orders.json")
ORDERS_NEW = os.path.join(OUTPUT_DIR, "new_orders.json")
STATE_FILE = "state.json"

# Síťové limity
CONNECT_READ_TIMEOUT_SEC = 25  # timeout pro urlopen (socket)
MAX_ATTEMPTS = 5               # retry pokusy
SLEEP_BASE = 2                 # exponenciální backoff: 2,4,8...

def log(msg: str):
    print(f"[fetch_orders] {msg}", flush=True)

def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                return d
        except Exception:
            pass
    return {"last_id_order": 0}

def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def build_url(password: str) -> str:
    # pozor: heslo je v query parametru, tak ať to zůstane stejné jako dřív
    return f"{API_BASE}?action=GetOrders&version=v2.0&password={password}"

def fetch_json(url: str) -> object:
    last_err = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            log(f"HTTP GET attempt {attempt}/{MAX_ATTEMPTS}")
            req = urllib.request.Request(url, headers={"User-Agent": "misdekor-gha"})
            with urllib.request.urlopen(req, timeout=CONNECT_READ_TIMEOUT_SEC) as r:
                raw = r.read()
            # některé servery vrací BOM / whitespace
            txt = raw.decode("utf-8", errors="replace").strip()
            data = json.loads(txt)
            return data
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as e:
            last_err = e
            wait = SLEEP_BASE * (2 ** (attempt - 1))
            log(f"ERROR: {type(e).__name__}: {e} (sleep {wait}s)")
            time.sleep(wait)
    raise RuntimeError(f"Failed to fetch/parse JSON after {MAX_ATTEMPTS} attempts: {last_err}")

def normalize_orders(raw: object) -> list[dict]:
    """
    Vrátí list objednávek jako dicty.
    Podpora:
      - list[dict]
      - dict wrapper s klíčem orders/data/items/...
    """
    data = raw

    if isinstance(data, dict):
        for k in ("orders", "data", "items", "result", "order_list", "list"):
            v = data.get(k)
            if isinstance(v, list):
                data = v
                break

    if not isinstance(data, list):
        # fallback: když je to dict bez známého klíče, zkus najít první list value
        if isinstance(raw, dict):
            for v in raw.values():
                if isinstance(v, list):
                    data = v
                    break

    if not isinstance(data, list):
        raise ValueError(f"Unexpected API JSON structure. Top={type(raw)}")

    cleaned: list[dict] = []
    for i, o in enumerate(data):
        if isinstance(o, dict):
            cleaned.append(o)
        elif isinstance(o, str):
            s = o.strip()
            if s.startswith("{") and s.endswith("}"):
                try:
                    obj = json.loads(s)
                    if isinstance(obj, dict):
                        cleaned.append(obj)
                        continue
                except Exception:
                    pass
            log(f"WARNING: skipping non-dict order at index {i} (string)")
        else:
            log(f"WARNING: skipping non-dict order at index {i} ({type(o)})")
    return cleaned

def order_id(o: dict) -> int:
    # Eshop-rychle obvykle id_order
    v = o.get("id_order") or o.get("id") or o.get("order_id")
    try:
        return int(v)
    except Exception:
        return 0

def main():
    password = os.environ.get("ESHOP_API_PASSWORD", "").strip()
    if not password:
        log("ERROR: ESHOP_API_PASSWORD is not set")
        sys.exit(1)

    mode = (os.environ.get("MODE") or "live").strip().lower()
    if mode not in ("live", "test"):
        mode = "live"

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    url = build_url(password)
    log(f"Mode: {mode}")
    log("Fetching orders from API...")
    raw = fetch_json(url)
    orders = normalize_orders(raw)
    log(f"Fetched orders: {len(orders)}")

    # ulož všechny
    with open(ORDERS_ALL, "w", encoding="utf-8") as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)

    state = load_state()
    last_id = 0
    try:
        last_id = int(state.get("last_id_order", 0))
    except Exception:
