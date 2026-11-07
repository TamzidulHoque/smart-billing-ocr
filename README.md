# Smart Billing with OCR

Upload a bill image, read it with Tesseract OCR, auto-fill the Billing form, check and save the bill, then find it again by the **bill ID printed on the image**.

Built with Django + Django REST Framework, JWT login (SimpleJWT), django-filter, Pillow and pytesseract. All data is fake.

## What is in the repo

| Path | What it is |
|---|---|
| `crm/` | Django project (`crm/crm`) and the `registration` app (models, API, OCR) |
| `crm/templates/`, `crm/static/` | Login, New Bill, Bills, Bill details and Customers pages |
| `bill_images/` | 20 fake bill images and `truth.json` (the values printed on each image) |
| `tools/make_bill_images.py` | Script that draws the 20 images and the demo customer fixture |
| `postman/Smart_Billing.postman_collection.json` | Postman collection for the full flow |
| `REPORT.md` | Image vs OCR vs database comparison for all 20 bills |

## Setup

You need Python 3.10+ and Tesseract OCR.

**Install Tesseract**

- Windows: install from <https://github.com/UB-Mannheim/tesseract/wiki> (or `winget install UB-Mannheim.TesseractOCR`).
- macOS: `brew install tesseract`
- Ubuntu/Debian: `sudo apt install tesseract-ocr`

The app finds Tesseract on `PATH`, in `C:\Program Files\Tesseract-OCR`, or in `%LOCALAPPDATA%\Programs\Tesseract-OCR`. Otherwise set `TESSERACT_CMD` in `.env` to the full path of `tesseract.exe`.

**Run the project**

```bash
git clone https://github.com/TamzidulHoque/smart-billing-ocr.git
cd smart-billing-ocr
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env            # macOS/Linux: cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Paste the printed value after `DJANGO_SECRET_KEY=` in `.env`. Then:

```bash
cd crm
python manage.py migrate
python manage.py loaddata demo_customers
python manage.py createsuperuser
python manage.py runserver 127.0.0.1:8001
```

Give the superuser an email address. The login API uses that email and password.

Open <http://127.0.0.1:8001/account/login/>.

## Pages

| URL | Page |
|---|---|
| `/account/login/` | JWT login |
| `/account/billing/` | Upload image → OCR → auto-filled form → check → save |
| `/account/bills/` | Bill list with search, customer and printed-date filters, ordering and pages |
| `/account/bills/B-1001/` | Bill details, loaded by printed bill ID |
| `/account/customers/` | Register customers and list them |

## API

Every API except login and token refresh needs `Authorization: Bearer <access token>`. Without it the response is `401`.

| Method | URL | Purpose |
|---|---|---|
| POST | `/account/api/login/` | `{"email", "password"}` → `access`, `refresh` |
| POST | `/account/api/token/refresh/` | `{"refresh"}` → new `access` |
| POST | `/account/api/ocr/` | form-data `image` → `full_text` and the six details plus `matched_customer` |
| GET, POST | `/account/api/registrations/` | List or register customers (`search`, `ordering`, `page`, `page_size`) |
| GET, POST | `/account/api/bills/` | List or save bills (form-data, includes `bill_image`) |
| GET | `/account/api/bills/<bill_id>/` | One bill by printed bill ID, e.g. `B-1001` |
| GET | `/account/api/bills/<bill_id>/image/` | The saved bill image |

**OCR response example**

```json
{
  "full_text": "DEMO MART\n...\nBill ID: B-1003\n...",
  "bill_id": "B-1003",
  "customer_name": "Nusrat Jahan",
  "mobile": "01000000003",
  "products": [{"name": "Green Tea 100g", "qty": 4, "amount": "880.00"}],
  "total_amount": "3580.00",
  "printed_at": "2026-10-05T12:25",
  "matched_customer": {"id": 3, "name": "Nusrat Jahan", "mobile": "01000000003", "matched_by": "name_and_mobile"}
}
```

A field OCR could not read is `null`. `matched_by` is `name_and_mobile`, `mobile` or `name`.

**Bill list parameters**

| Param | Example | Meaning |
|---|---|---|
| `search` | `B-1001` or `rahim` | Bill ID or customer name, partial and case-insensitive |
| `customer` | `1` | Customer ID |
| `printed_from` | `2026-10-01` | Printed on or after this date |
| `printed_to` | `2026-10-10` | Printed on or before this date |
| `ordering` | `-total_amount` | `bill_id`, `printed_at`, `total_amount`, `created_at`; `-` for descending |
| `page`, `page_size` | `2`, `5` | Pages, up to 100 per page |

`printed_at` is the date and time printed on the bill. `created_at` is when the record was saved.

## Postman

Import `postman/Smart_Billing.postman_collection.json`. In the collection variables, set `email` and `password`. Then run:

1. **Login**: saves `access_token` automatically
2. **No token → 401**
3. **OCR: upload bill image**: choose a file from `bill_images/` for `image`; the result fills the next request's variables
4. **Save bill**: choose the same file for `bill_image`
5. **Get bill by printed bill ID**
6. Search, filter, ordering and page requests

## Comparison report

`REPORT.md` compares, for each bill, the image, the OCR text and fields, and the saved database values, and marks what matched.

```bash
cd crm
python manage.py load_demo_bills
python manage.py bill_report
```

`load_demo_bills` reads each image with OCR and saves it. It uses `truth.json` in place of the person who checks the form. Bills already saved are skipped. `bill_report` writes `REPORT.md`.

To redraw the images and the customer fixture: `python tools/make_bill_images.py`.

## Tests

```bash
cd crm
python manage.py test registration
```
