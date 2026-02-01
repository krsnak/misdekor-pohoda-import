import json
import os

INPUT = "output/new_orders.json"
OUTPUT = "output/pohoda.xml"


def main() -> None:
    if not os.path.exists(INPUT):
        print("No new_orders.json found")
        return

    with open(INPUT, "r", encoding="utf-8") as f:
        orders = json.load(f)

    if not orders:
        print("No new orders")
        return

    # vezmeme první objednávku
    o = orders[0]

    order_number = o.get("number", "")
    customer = o["customer"]["billing_information"].get("name", "")

    # vezmeme první položku objednávky
    row_list = o.get("row_list", [])
    if not row_list:
        print("Order has no row_list items")
        return

    item = row_list[0]
    product_name = item.get("product_name", "")
    qty = item.get("count", 1)
    price = item.get("price_per_unit_with_vat", 0)

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<dataPack>
  <dataPackItem>
    <order>
      <orderHeader>
        <number>{order_number}</number>
        <text>Objednávka z e-shopu</text>
        <partnerIdentity>
          <address>
            <name>{customer}</name>
          </address>
        </partnerIdentity>
      </orderHeader>

      <orderDetail>
        <orderItem>
          <text>{product_name}</text>
          <quantity>{qty}</quantity>
          <unitPrice>{price}</unitPrice>
        </orderItem>
      </orderDetail>

    </order>
  </dataPackItem>
</dataPack>
"""

    os.makedirs("output", exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(xml)

    print("Saved output/pohoda.xml with 1 item")


if __name__ == "__main__":
    main()
