import json
import os
from xml.sax.saxutils import escape

INPUT = "output/new_orders.json"
OUTPUT = "output/pohoda.xml"

POHODA_ICO = "12345678"


def main() -> None:
    # 1) Musí existovat new_orders.json
    if not os.path.exists(INPUT):
        print("No new_orders.json found")
        return

    # 2) Načteme nové objednávky
    with open(INPUT, "r", encoding="utf-8") as f:
        orders = json.load(f)

    if not orders:
        print("No new orders -> nothing to export")
        return

    # 3) Vezmeme první objednávku (zatím test)
    o = orders[0]

    order_number = str(o.get("number", ""))
    customer = o.get("customer", {}).get("billing_information", {}).get("name", "")

    row_list = o.get("row_list", [])
    if not row_list:
        print("Order has no items")
        return

    item = row_list[0]
    product_name = item.get("product_name", "")
    qty = item.get("count", 1)
    price = item.get("price_per_unit_with_vat", 0)

    # Escape textů pro XML
    order_number_xml = escape(order_number)
    customer_xml = escape(customer)
    product_xml = escape(product_name)

    # 4) POHODA XML obálka + jedna položka
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<dat:dataPack
  xmlns:dat="http://www.stormware.cz/schema/version_2/data.xsd"
  xmlns:ord="http://www.stormware.cz/schema/version_2/order.xsd"
  xmlns:typ="http://www.stormware.cz/schema/version_2/type.xsd"
  id="MISDEKOR_IMPORT"
  version="2.0"
  ico="{POHODA_ICO}"
  application="misdekor-import"
  note="Import objednávek z Eshop-rychle">

  <dat:dataPackItem id="{order_number_xml}" version="2.0">
    <ord:order version="2.0">
      <ord:orderHeader>
        <ord:number>{order_number_xml}</ord:number>
        <ord:text>Objednávka z e-shopu</ord:text>

        <ord:partnerIdentity>
          <typ:address>
            <typ:name>{customer_xml}</typ:name>
          </typ:address>
        </ord:partnerIdentity>
      </ord:orderHeader>

      <ord:orderDetail>
        <ord:orderItem>
          <ord:text>{product_xml}</ord:text>
          <ord:quantity>{qty}</ord:quantity>
          <ord:unitPrice>{price}</ord:unitPrice>
        </ord:orderItem>
      </ord:orderDetail>

    </ord:order>
  </dat:dataPackItem>

</dat:dataPack>
"""

    os.makedirs("output", exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(xml)

    print("Saved output/pohoda.xml (correct generator)")


if __name__ == "__main__":
    main()
