import json
import os

INPUT = "output/new_orders.json"
OUTPUT = "output/pohoda.xml"


def main():
    if not os.path.exists(INPUT):
        print("No new_orders.json found")
        return

    with open(INPUT, "r", encoding="utf-8") as f:
        orders = json.load(f)

    if not orders:
        print("No new orders")
        return

    # vezmeme jen první objednávku
    o = orders[0]

    order_number = o.get("number")
    customer = o["customer"]["billing_information"]["name"]

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
    </order>
  </dataPackItem>
</dataPack>
"""

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(xml)

    print("Saved output/pohoda.xml")


if __name__ == "__main__":
    main()
