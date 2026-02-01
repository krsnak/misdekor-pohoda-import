import json
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from xml.sax.saxutils import escape

INPUT = "output/new_orders.json"
OUTPUT = "output/pohoda.xml"

ICO = "12345678"


def to_date_yyyy_mm_dd(value: str | None) -> str:
    """
    Pokusí se vytáhnout datum z API (různé formáty), jinak vezme dnešek.
    Pohoda chce typicky YYYY-MM-DD.
    """
    if not value:
        return datetime.now().strftime("%Y-%m-%d")

    # nejčastěji bývá "2026-02-01 12:34:56" nebo ISO
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value[:19], fmt).strftime("%Y-%m-%d")
        except Exception:
            pass

    return datetime.now().strftime("%Y-%m-%d")


def dec2(value, default="0.00") -> str:
    """
    Bezpečně zkonvertuje na Decimal a naformátuje na 2 desetinná místa s tečkou.
    """
    try:
        d = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        # vždy tečka, žádné tisícové oddělovače
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
        order_number = o.get("number") or str(order_id or "").strip()
        pack_item_id = f"ORDER_{order_id or order_number or 'UNKNOWN'}"

        billing = get_billing(o)
        name = billing.get("name", "") or ""
        street = billing.get("street", "") or ""
        city = billing.get("city", "") or ""
        zip_code = billing.get("zip", "") or ""
        ico = billing.get("ico", "") or ""   # pokud ho API dává
        dic = billing.get("dic", "") or ""   # pokud ho API dává

        # datum z objednávky (názvy polí se můžou lišit – zkusíme pár variant)
        date_val = (
            o.get("date")
            or o.get("date_add")
            or o.get("created")
            or o.get("created_at")
            or ""
        )
        doc_date = to_date_yyyy_mm_dd(str(date_val) if date_val is not None else None)

        # položky
        row_list = o.get("row_list", []) or []
        if not isinstance(row_list, list) or not row_list:
            # objednávka bez položek radši přeskočit
            continue

        order_items_parts: list[str] = []
        for r in row_list:
            product_name = (r.get("product_name") or r.get("name") or "").strip()
            qty = int_or(r.get("count", 1), default=1)

            # ceny jsou s DPH → bereme unitPrice jako s DPH (homeCurrency/unitPrice)
            price = r.get("price_per_unit_with_vat", None)
            if price is None:
                price = r.get("price_with_vat", None)
            if price is None:
                price = r.get("price", 0)

            product_xml = escape(product_name) if product_name else "Položka"
            unit_price = dec2(price)

            order_items_parts.append(
                f"""
        <ord:orderItem>
          <ord:text>{product_xml}</ord:text>
          <ord:quantity>{qty}</ord:quantity>
          <ord:homeCurrency>
            <typ:unitPrice>{unit_price}</typ:unitPrice>
          </ord:homeCurrency>
        </ord:orderItem>""".rstrip()
            )

        customer_xml = escape(name) if name else "Zákazník"

        # Adresa – držíme se minima. (Name je nejdůležitější.)
        address_parts = [f"<typ:name>{customer_xml}</typ:name>"]
        if street:
            address_parts.append(f"<typ:street>{escape(street)}</typ:street>")
        if city:
            address_parts.append(f"<typ:city>{escape(city)}</typ:city>")
        if zip_code:
            address_parts.append(f"<typ:zip>{escape(zip_code)}</typ:zip>")
        if ico:
            address_parts.append(f"<typ:ico>{escape(str(ico))}</typ:ico>")
        if dic:
            address_parts.append(f"<typ:dic>{escape(str(dic))}</typ:dic>")

        address_xml = "\n            ".join(address_parts)

        # Pozn.: ord:number jsme dřív odstranili (Pohoda to nechce jako plain text).
        # Pokud budeš chtít svázat číslo objednávky, dává se to obvykle do textu/poznámky.
        note_text = f"Objednávka z e-shopu {order_number}".strip()
        note_xml = escape(note_text)

        items_xml.append(
            f"""
  <dat:dataPackItem id="{escape(pack_item_id)}" version="2.0">
    <ord:order version="2.0">

      <ord:orderHeader>
        <ord:orderType>receivedOrder</ord:orderType>
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


if __name__ == "__main__":
    main()
