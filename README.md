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
<dataPack id="IMPORT" version="2.0" ico="12345678">
  <dataPackItem id="ORDER_XXXX_TIMESTAMP">
    <order>
      <orderHeader>
        <orderType>receivedOrder</orderType>
        <numberOrder>ORDER_NUMBER</numberOrder>
        <date>2026-01-01</date>
      </orderHeader>
      <orderDetail>
        <orderItem>
          <text>Produkt A</text>
          <quantity>2</quantity>
          <unitPrice>100.00</unitPrice>
        </orderItem>
      </orderDetail>
    </order>
  </dataPackItem>
</dataPack>
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
