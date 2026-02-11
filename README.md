# misdekor-pohoda-import

Automatický import objednávek z **Eshop-rychle.cz API** do účetního
systému **POHODA (Stormware)**.

------------------------------------------------------------------------

## 🧠 Architektura

Eshop-rychle API\
↓\
fetch_orders.py\
↓\
new_orders.json\
↓\
make_pohoda_xml.py\
↓\
pohoda.xml\
↓\
Email (GitHub Actions)

------------------------------------------------------------------------

## 📁 Struktura projektu

.github/workflows/fetch.yml\
scripts/fetch_orders.py\
scripts/make_pohoda_xml.py\
state.json

------------------------------------------------------------------------

## ⚙ Jak to funguje

### 1️⃣ Načítání objednávek

-   Volá Eshop-rychle API: `?action=GetOrders&version=v2.0&password=...`
-   API vrací max 20 objednávek
-   Filtruje objednávky podle: `id_order > last_id_order`
-   Ukládá nové objednávky do `output/new_orders.json`
-   Aktualizuje `state.json`

### 2️⃣ Generování XML

-   Generuje dokument typu: `receivedOrder`
-   Každá objednávka = jeden `<dataPackItem>`

------------------------------------------------------------------------

## 📄 Ukázka generovaného XML

``` xml
<?xml version="1.0" encoding="UTF-8"?>
<dat:dataPack
  xmlns:dat="http://www.stormware.cz/schema/version_2/data.xsd"
  xmlns:ord="http://www.stormware.cz/schema/version_2/order.xsd"
  xmlns:typ="http://www.stormware.cz/schema/version_2/type.xsd"
  id="MISDEKOR_IMPORT"
  version="2.0"
  ico="12345678"
  application="misdekor-import"
  note="Import objednávek z Eshop-rychle">

  <dat:dataPackItem id="ORDER_XXXX_TIMESTAMP" version="2.0">
    <ord:order version="2.0">

      <ord:orderHeader>
        <ord:orderType>receivedOrder</ord:orderType>
        <ord:numberOrder>ORDER_NUMBER</ord:numberOrder>
        <ord:date>2026-01-01</ord:date>
        <ord:text>Objednávka z e-shopu ORDER_NUMBER</ord:text>

        <ord:partnerIdentity>
          <typ:address>
            <typ:name>TEST CUSTOMER</typ:name>
            <typ:street>Testovací ulice 123</typ:street>
            <typ:city>Testovací město</typ:city>
            <typ:zip>00000</typ:zip>
          </typ:address>
        </ord:partnerIdentity>

      </ord:orderHeader>

      <ord:orderDetail>
        <ord:orderItem>
          <ord:text>Produkt A</ord:text>
          <ord:quantity>2</ord:quantity>
          <ord:unit>ks</ord:unit>
          <ord:homeCurrency>
            <typ:unitPrice>100.00</typ:unitPrice>
          </ord:homeCurrency>
        </ord:orderItem>
      </ord:orderDetail>

    </ord:order>
  </dat:dataPackItem>
</dat:dataPack>
```

------------------------------------------------------------------------

## 🏪 Sklad

V make_pohoda_xml.py:

USE_STOCK = False\
DEFAULT_STORE_IDS = "1"

Pokud USE_STOCK = True, generuje se `<stockItem>` podle product_number.

------------------------------------------------------------------------

## 🔄 Stavový systém

state.json:

{ "last_id_order": 1590 }

-   Importují se jen objednávky s vyšším ID.
-   Při nových objednávkách se hodnota automaticky aktualizuje.
-   Pro reset nastav: last_id_order = poslední_ID - 1

------------------------------------------------------------------------

## 🚀 Spuštění

### GitHub Actions

Workflow: `.github/workflows/fetch.yml`\
Spouští se ručně nebo každou hodinu.

### Lokálně

export ESHOP_API_PASSWORD=...\
python scripts/fetch_orders.py\
python scripts/make_pohoda_xml.py

------------------------------------------------------------------------

## 📧 Email konfigurace

GitHub Secrets:

SMTP_SERVER\
SMTP_PORT\
SMTP_USERNAME\
SMTP_PASSWORD\
MAIL_TO\
MAIL_FROM

------------------------------------------------------------------------

## 📌 Omezení

-   API vrací max 20 objednávek
-   Generuje pouze receivedOrder
-   Nepodporuje cenové hladiny
-   Nepodporuje více skladů

------------------------------------------------------------------------

## Licence

MIT
