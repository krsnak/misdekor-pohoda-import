import json
import os
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from xml.sax.saxutils import escape

INPUT = "output/new_orders.json"
OUTPUT = "output/pohoda.xml"

ICO = "27201694"

# =========================
# PŘEPÍNAČ: sklad / bez skladu
# =========================
USE_STOCK = False
DEFAULT_STORE_IDS = "1"

# limity textů kvůli validaci
TEXT_MAX_LEN_ITEM = 100
TEXT_MAX_LEN_NOTE = 80


# -------------------------
# HELPERS
# -------------------------

def safe_text(value: str, max_len: int) -> str:
    """Ořízne text + XML escape."""
    s = (value or "").strip()
    if not s:
        return ""
    if len(s) > max_len:
        s = s[: max_len - 1].rstrip() + "…"
    return escape(s)


def simplify_delivery_name(name: str) -> str:
    """Zkrátí dopravu na první dvě části."""
    s = (name or "").strip()
    if not s:
        return ""
    parts = [p.strip() for p in s.split(" - ")]
    if len(parts) >= 2:
        return " - ".join(parts[:2])
    return s


def sanitize_pack_item_id(value: str) -> str:
    """Bezpečný ID string pro POHODU."""
    s = (value or "").strip()
    if not s:
        return "UNKNOWN"
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^A-Za-z0-9._-]", "_", s)
    return s or "UNKNOWN"


def to_date_yyyy_mm_dd(value) -> str:
    """Pohoda chce YYYY-MM-DD."""
    if not value:
        return datetime.now().strftime("%Y-%m-%d")

    if isinstance(value, dict):
        value = value.get("date") or value.get("datetime") or ""

    s = str(value)[:19]

    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except Exception:
            pass

    return datetime.now().strftime("%Y-%m-%d")


def dec2(value, default="0.00") -> str:
    """Decimal na 2 místa."""
    try:
        d = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return f"{d:.2f}"
    except (InvalidOperation, ValueError, TypeError):
        return default


def int_or(value, default=1) -> int:
    try:
        return int(value)
    except Exception:
        return default


# -------------------------
# NORMALIZE INPUT
# -------------------------

def find_first_list(obj):
    """Najde první list uvnitř wrapper dictu."""
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for key in ("orders", "order_list", "data", "items", "result"):
            if key in obj and isinstance(obj[key], list):
                return obj[key]
        for v in obj.values():
            if isinstance(v, list):
                return v
            if isinstance(v, dict):
                sub = find_first_list(v)
                if isinstance(sub, list):
                    return sub
    return None


def load_orders():
    """Načte new_orders.json vždy jako list[dict]."""
    with open(INPUT, "r", encoding="utf-8") as f:
        raw = json.load(f)

    lst = find_first_list(raw)
    if not isinstance(lst, list):
        raise ValueError("Unexpected JSON structure in new_orders.json")

    return [o for o in lst if isinstance(o, dict)]


# -------------------------
# MAIN
# -------------------------

def main():
    if not os.path.exists(INPUT):
        print("No new_orders.json found")
        return

    orders = load_orders()

    if not orders:
        print("No new orders")
        return

    items_xml = []

    # timestamp pro unikátní ID importu
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")

    for o in orders:
        order_id = o.get("id_order")
        order_number = (o.get("number") or str(order_id or "")).strip()

        # unikátní dataPackItem id
        raw_id = f"ORDER_{order_id or order_number}_{stamp}"
        pack_item_id = sanitize_pack_item_id(raw_id)

        # billing info
        billing = (o.get("customer", {}) or {}).get("billing_information", {}) or {}

        name = (billing.get("name") or "").strip()
        street = (billing.get("street") or "").strip()
        city = (billing.get("city") or "").strip()
        zip_code = (billing.get("zip") or "").strip()

        # ZIP normalizace (odstraní mezery)
        zip_code = zip_code.replace(" ", "")

        # datum objednávky
        date_val = (
            o.get("created")
            or o.get("origin", {}).get("date")
            or o.get("date")
            or o.get("date_add")
            or o.get("created_at")
            or ""
        )
        doc_date = to_date_yyyy_mm_dd(date_val)

        # doprava / platba
        delivery = o.get("delivery", {}) or {}
        payment = o.get("payment", {}) or {}

        delivery_name = simplify_delivery_name(delivery.get("nazev_postovne") or "")
        delivery_price = delivery.get("postovne", 0)

        payment_name = (payment.get("nazev_platba") or "").strip()
        payment_price = payment.get("castka_platba", 0)

        # položky zboží
        row_list = o.get("row_list", []) or []
        if not isinstance(row_list, list) or not row_list:
            continue

        order_items_parts = []

        # --- ZBOŽÍ ---
        for r in row_list:
            if not isinstance(r, dict):
                continue

            product_name = (r.get("product_name") or r.get("name") or "").strip()
            product_code = (r.get("product_number") or "").strip()

            qty = int_or(r.get("count", 1))
            unit = (r.get("unit") or "").strip()

            price = (
                r.get("price_per_unit_with_vat")
                or r.get("price_with_vat")
                or r.get("price")
                or 0
            )

            unit_price = dec2(price)
            product_xml = safe_text(product_name, TEXT_MAX_LEN_ITEM) or "Položka"

            unit_xml = f"\n          <ord:unit>{escape(unit)}</ord:unit>" if unit else ""

            code_xml = ""
            stock_xml = ""

            if USE_STOCK and product_code:
                code_xml = f"\n          <ord:code>{escape(product_code)}</ord:code>"
                stock_xml = f"""
          <ord:stockItem>
            <typ:store>
              <typ:ids>{escape(DEFAULT_STORE_IDS)}</typ:ids>
            </typ:store>
            <typ:stockItem>
              <typ:ids>{escape(product_code)}</typ:ids>
            </typ:stockItem>
          </ord:stockItem>""".rstrip()

            order_items_parts.append(
                f"""
        <ord:orderItem>
          <ord:text>{product_xml}</ord:text>
          <ord:quantity>{qty}</ord:quantity>{unit_xml}
          <ord:homeCurrency>
            <typ:unitPrice>{unit_price}</typ:unitPrice>
          </ord:homeCurrency>{code_xml}{stock_xml}
        </ord:orderItem>""".rstrip()
            )

        # --- DOPRAVA ---
        try:
            if delivery_name and Decimal(str(delivery_price or 0)) > 0:
                order_items_parts.append(
                    f"""
        <ord:orderItem>
          <ord:text>{safe_text(delivery_name, 60)}</ord:text>
          <ord:quantity>1</ord:quantity>
          <ord:homeCurrency>
            <typ:unitPrice>{dec2(delivery_price)}</typ:unitPrice>
          </ord:homeCurrency>
        </ord:orderItem>""".rstrip()
                )
        except Exception:
            pass

        # --- DOBÍRKA / PLATBA ---
        try:
            if payment_name and Decimal(str(payment_price or 0)) > 0:
                order_items_parts.append(
                    f"""
        <ord:orderItem>
          <ord:text>{safe_text(payment_name, 60)}</ord:text>
          <ord:quantity>1</ord:quantity>
          <ord:homeCurrency>
            <typ:unitPrice>{dec2(payment_price)}</typ:unitPrice>
          </ord:homeCurrency>
        </ord:orderItem>""".rstrip()
                )
        except Exception:
            pass

        # partner identity
        address_parts = [f"<typ:name>{escape(name) if name else 'Zákazník'}</typ:name>"]
        if street:
            address_parts.append(f"<typ:street>{escape(street)}</typ:street>")
        if city:
            address_parts.append(f"<typ:city>{escape(city)}</typ:city>")
        if zip_code:
            address_parts.append(f"<typ:zip>{escape(zip_code)}</typ:zip>")

        address_xml = "\n            ".join(address_parts)

        note_text = f"Objednávka z e-shopu {order_number}"
        note_xml = safe_text(note_text, TEXT_MAX_LEN_NOTE)

        number_order_xml = (
            f"\n        <ord:numberOrder>{escape(order_number)}</ord:numberOrder>"
            if order_number
            else ""
        )

        # !!! paymentType odstraněno úplně !!!

        items_xml.append(
            f"""
  <dat:dataPackItem id="{escape(pack_item_id)}" version="2.0">
    <ord:order version="2.0">

      <ord:orderHeader>
        <ord:orderType>receivedOrder</ord:orderType>{number_order_xml}
        <ord:date>{doc_date}</ord:date>
        <ord:text>{note_xml}</ord:text>

        <ord:partnerIdentity>
          <typ:address>
            {address_xml}
          </typ:address>
        </ord:partnerIdentity>

      </ord:orderHeader>

      <ord:orderDetail>
{chr(10).join(order_items_parts)}
      </ord:orderDetail>

    </ord:order>
  </dat:dataPackItem>""".rstrip()
        )

    if not items_xml:
        print("No valid orders with items")
        return

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<dat:dataPack
  xmlns:dat="http://www.stormware.cz/schema/version_2/data.xsd"
  xmlns:ord="http://www.stormware.cz/schema/version_2/order.xsd"
  xmlns:typ="http://www.stormware.cz/schema/version_2/type.xsd"
  id="MISDEKOR_IMPORT"
  version="2.0"
  ico="{ICO}"
  application="misdekor-import"
  note="Import objednávek z Eshop-rychle">

{chr(10).join(items_xml)}

</dat:dataPack>
"""

    os.makedirs("output", exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(xml)

    print(f"Saved {OUTPUT} (orders: {len(items_xml)})")


if __name__ == "__main__":
    main()
