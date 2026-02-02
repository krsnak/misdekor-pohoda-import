import json
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from xml.sax.saxutils import escape

INPUT = "output/new_orders.json"
OUTPUT = "output/pohoda.xml"

ICO = "09405399"

# ====== PŘEPÍNAČ ======
# False = NEPOSÍLAT stockItem (nebude to hledat sklad → bez warningu "Zásoba neexistuje")
# True  = POSÍLAT stockItem (párování na skladovou zásobu podle kódu)
USE_STOCK = False

# podle vzoru z Eshop-rychle (typ:store -> typ:ids)
DEFAULT_STORE_IDS = "1"

# bezpečné limity pro ord:text
TEXT_MAX_LEN_ITEM = 100
TEXT_MAX_LEN_NOTE = 80
TEXT_MAX_LEN_PAYMENT_IDS = 60


def safe_text(value: str, max_len: int) -> str:
    """Ořízne text na max_len, přidá … a provede XML escape."""
    s = (value or "").strip()
    if not s:
        return ""
    if len(s) > max_len:
        s = s[: max_len - 1].rstrip() + "…"
    return escape(s)


def simplify_delivery_name(name: str) -> str:
    """
    Z dopravy zahodí detail výdejního místa.
    "DPD ParcelShop CZ - Na výdejní místo - Tábor, ... ([CZ31044])"
    -> "DPD ParcelShop CZ - Na výdejní místo"
    """
    s = (name or "").strip()
    if not s:
        return ""

    parts = [p.strip() for p in s.split(" - ")]
    if len(parts) >= 2:
        return " - ".join(parts[:2])  # značka + typ (bez adresy boxu)
    return s


def to_date_yyyy_mm_dd(value) -> str:
    """Vytáhne datum z API, jinak vezme dnešek. Pohoda chce YYYY-MM-DD."""
    if not value:
        return datetime.now().strftime("%Y-%m-%d")

    # Eshop-rychle často posílá dict {date: "...", timezone...}
    if isinstance(value, dict):
        value = value.get("date") or value.get("datetime") or ""

    s = str(value)
    s19 = s[:19]

    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s19, fmt).strftime("%Y-%m-%d")
        except Exception:
            pass

    return datetime.now().strftime("%Y-%m-%d")


def dec2(value, default="0.00") -> str:
    """Decimal na 2 desetinná místa, vždy s tečkou."""
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


def get_billing(o: dict) -> dict:
    return (o.get("customer", {}) or {}).get("billing_information", {}) or {}


def get_delivery(o: dict) -> dict:
    return o.get("delivery", {}) or {}


def get_payment(o: dict) -> dict:
    return o.get("payment", {}) or {}


def main() -> None:
    if not os.path.exists(INPUT):
        print("No new_orders.json found")
        return

    with open(INPUT, "r", encoding="utf-8") as f:
        orders = json.load(f)

    if not orders:
        print("No new orders")
        return

    items_xml: list[str] = []

    for o in orders:
        order_id = o.get("id_order")
        order_number = (o.get("number") or str(order_id or "")).strip()
        pack_item_id = f"ORDER_{order_id or order_number or 'UNKNOWN'}"

        billing = get_billing(o)
        name = (billing.get("name", "") or "").strip()
        street = (billing.get("street", "") or "").strip()
        city = (billing.get("city", "") or "").strip()
        zip_code = (billing.get("zip", "") or "").strip()
        ico = (billing.get("ico", "") or "").strip()
        dic = (billing.get("dic", "") or "").strip()

        # datum z objednávky (z tvého JSONu to často bývá o["created"]["date"] nebo origin.date.date)
        date_val = (
            o.get("created")
            or (o.get("origin", {}) or {}).get("date")
            or o.get("date")
            or o.get("date_add")
            or o.get("created_at")
            or ""
        )
        doc_date = to_date_yyyy_mm_dd(date_val)

        # doprava / platba z JSONu
        delivery = get_delivery(o)
        payment = get_payment(o)

        delivery_name_full = (delivery.get("nazev_postovne") or "").strip()
        delivery_name = simplify_delivery_name(delivery_name_full)
        delivery_price = delivery.get("postovne", 0)

        payment_name = (payment.get("nazev_platba") or "").strip()
        payment_price = payment.get("castka_platba", 0)

        # položky zboží
        row_list = o.get("row_list", []) or []
        if not isinstance(row_list, list) or not row_list:
            continue

        order_items_parts: list[str] = []

        # ===== ZBOŽÍ =====
        for r in row_list:
            product_name = (r.get("product_name") or r.get("name") or "").strip()
            product_code = (r.get("product_number") or "").strip()
            qty = int_or(r.get("count", 1), default=1)
            unit = (r.get("unit") or "").strip()

            # ceny jsou s DPH → unitPrice bereme s DPH
            price = r.get("price_per_unit_with_vat", None)
            if price is None:
                price = r.get("price_with_vat", None)
            if price is None:
                price = r.get("price", 0)

            unit_price = dec2(price)
            product_xml = safe_text(product_name, TEXT_MAX_LEN_ITEM) or "Položka"

            unit_xml = f"\n          <ord:unit>{escape(unit)}</ord:unit>" if unit else ""

            code_xml = ""
            stock_xml = ""

            # Kód položky může být užitečný i bez skladu (kvůli dohledání)
            if product_code:
                code_xml = f"\n          <ord:code>{escape(product_code)}</ord:code>"

                # ====== skladem / bez skladu podle přepínače ======
                if USE_STOCK:
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

        # ===== DOPRAVA =====
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

        # ===== DOBÍRKA / PLATEBNÍ POPLATEK =====
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

        # Partner
        customer_xml = escape(name) if name else "Zákazník"
        address_parts = [f"<typ:name>{customer_xml}</typ:name>"]
        if street:
            address_parts.append(f"<typ:street>{escape(street)}</typ:street>")
        if city:
            address_parts.append(f"<typ:city>{escape(city)}</typ:city>")
        if zip_code:
            address_parts.append(f"<typ:zip>{escape(zip_code)}</typ:zip>")
        if ico:
            address_parts.append(f"<typ:ico>{escape(ico)}</typ:ico>")
        if dic:
            address_parts.append(f"<typ:dic>{escape(dic)}</typ:dic>")

        address_xml = "\n            ".join(address_parts)

        # Header text + číslo objednávky
        note_text = f"Objednávka z e-shopu {order_number}".strip()
        note_xml = safe_text(note_text, TEXT_MAX_LEN_NOTE) or escape(note_text)

        number_order_xml = f"\n        <ord:numberOrder>{escape(order_number)}</ord:numberOrder>" if order_number else ""

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
        print("No valid orders with items to export")
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

    print(f"Saved {OUTPUT} (items: {len(items_xml)})")
    print(f"USE_STOCK = {USE_STOCK}")


if __name__ == "__main__":
    main()
