import json
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from xml.sax.saxutils import escape

INPUT = "output/new_orders.json"
OUTPUT = "output/pohoda.xml"

ICO = "12345678"

# podle vzoru z Eshop-rychle (typ:store -> typ:ids)
DEFAULT_STORE_IDS = "1"


def to_date_yyyy_mm_dd(value) -> str:
    """
    Vytáhne datum z API, jinak vezme dnešek. Pohoda typicky chce YYYY-MM-DD.
    Umí zpracovat i strukturu:
      {"date":"2026-01-27 21:34:01.000000", "timezone":"Europe/Prague", ...}
    """
    if not value:
        return datetime.now().strftime("%Y-%m-%d")

    # Eshop-rychle často posílá dict {date: "..."}
    if isinstance(value, dict):
        value = value.get("date") or value.get("datetime") or ""

    s = str(value)

    # "2026-01-27 21:34:01.000000" -> bereme prvních 19 znaků
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

        # datum – v tvém JSONu je to typicky o["created"]["date"]
        date_val = (
            o.get("created")
            or o.get("origin", {}).get("date")
            or o.get("date")
            or o.get("date_add")
            or o.get("created_at")
            or ""
        )
        doc_date = to_date_yyyy_mm_dd(date_val)

        # doprava/platba z JSONu
        delivery = get_delivery(o)
        payment = get_payment(o)

        delivery_name = (delivery.get("nazev_postovne") or "").strip()
        delivery_price = delivery.get("postovne", 0)

        payment_name = (payment.get("nazev_platba") or "").strip()
        payment_price = payment.get("castka_platba", 0)

        # položky zboží
        row_list = o.get("row_list", []) or []
        if not isinstance(row_list, list) or not row_list:
            continue

        order_items_parts: list[str] = []

        for r in row_list:
            product_name = (r.get("product_name") or r.get("name") or "").strip()
            product_code = (r.get("product_number") or "").strip()
            qty = int_or(r.get("count", 1), default=1)
            unit = (r.get("unit") or "").strip()

            # ceny jsou s DPH → bereme unitPrice jako s DPH
            price = r.get("price_per_unit_with_vat", None)
            if price is None:
                price = r.get("price_with_vat", None)
            if price is None:
                price = r.get("price", 0)

            unit_price = dec2(price)
            product_xml = escape(product_name) if product_name else "Položka"

            # skladová položka, pokud máme kód produktu (product_number)
            stock_xml = ""
            code_xml = ""
            unit_xml = f"\n          <ord:unit>{escape(unit)}</ord:unit>" if unit else ""

            if product_code:
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

        # doprava jako textová položka
        if delivery_name and Decimal(str(delivery_price or 0)) > 0:
            order_items_parts.append(
                f"""
        <ord:orderItem>
          <ord:text>{escape(delivery_name)}</ord:text>
          <ord:quantity>1</ord:quantity>
          <ord:homeCurrency>
            <typ:unitPrice>{dec2(delivery_price)}</typ:unitPrice>
          </ord:homeCurrency>
        </ord:orderItem>""".rstrip()
            )

        # dobírka/platba jako textová položka
        if payment_name and Decimal(str(payment_price or 0)) > 0:
            order_items_parts.append(
                f"""
        <ord:orderItem>
          <ord:text>{escape(payment_name)}</ord:text>
          <ord:quantity>1</ord:quantity>
          <ord:homeCurrency>
            <typ:unitPrice>{dec2(payment_price)}</typ:unitPrice>
          </ord:homeCurrency>
        </ord:orderItem>""".rstrip()
            )

        # partner
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

        # text do dokladu + numberOrder
        note_text = f"Objednávka z e-shopu {order_number}".strip()
        note_xml = escape(note_text)

        number_order_xml = ""
        if order_number:
            number_order_xml = f"\n        <ord:numberOrder>{escape(order_number)}</ord:numberOrder>"

        # paymentType do headeru (styl jako Eshop-rychle)
        payment_type_xml = ""
        if payment_name:
            payment_type_xml = f"""
        <ord:paymentType>
          <typ:ids>{escape(payment_name)}</typ:ids>
          <typ:paymentType>delivery</typ:paymentType>
        </ord:paymentType>""".rstrip()

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
        </ord:partnerIdentity>{payment_type_xml}
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


if __name__ == "__main__":
    main()
