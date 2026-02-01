import json
import os
from xml.sax.saxutils import escape

INPUT = "output/new_orders.json"
OUTPUT = "output/pohoda.xml"

POHODA_ICO = "12345678"   # testovací firma


def main() -> None:
    if not os.path.exists(INPUT):
        print("No new_orders.json found")
        return

    with open(INPUT, "r", encoding="utf-8") as f:
        orders = json.load(f)

    if not orders:
        print("No new orders")
        return

    o = orders[0]

    order_id = str(o.get("number", "ESHOP_ORDER"))  # použijeme jako ID balíčku
    customer = o.get("customer", {}).get("billing_information", {}).get("name", "")

    row_list = o.get("row_list", [])
    if not row_list:
        print("Order has no row_list items")
        return

    item = row_list[0]
    product_name = item.get("product_name", "")
    qty = item.get("count", 1)
    price = item.get("price_per_unit_with_vat", 0)

    # XML-safe
    order_id_xml = escape(order_id)
    customer_xml = escape(customer)
    product_xml = escape(product_name)

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

  <dat:dataPackItem id="{order_id_xml}" version="2.0">
    <ord:order version="2.0">
      <ord:orderHeader>
        <!-- ord:number schválně NEPOSÍLÁME (POHODA Start to často odmítá v tomto tvaru).
             POHODA si číslo objednávky přidělí sama podle číselné řady. -->
        <ord:text>Objednávka z e-shopu {order_id_xml}</ord:text>

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

    print("Saved output/pohoda.xml (without ord:number)")


if __name__ == "__main__":
    main()
