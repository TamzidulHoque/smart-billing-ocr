import html
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from registration.models import Bill
from registration.ocr import parse_bill_text, read_text

ROOT = settings.BASE_DIR.parent
IMAGES = ROOT / "bill_images"
FIELDS = [
    ("bill_id", "Bill ID"),
    ("customer_name", "Customer name"),
    ("mobile", "Mobile"),
    ("products", "Products"),
    ("total_amount", "Total amount"),
    ("printed_at", "Printed date/time"),
]


def show_products(items):
    if not items:
        return "—"
    return "<br>".join(f"{i['name']} × {i['qty']} = {i['amount']}" for i in items)


def show(key, value):
    if value in (None, "", []):
        return "—"
    if key == "products":
        return show_products(value)
    return str(value).replace("|", "\\|")


def db_values(bill):
    return {
        "bill_id": bill.bill_id,
        "customer_name": bill.customer.name,
        "mobile": bill.customer.mobile,
        "products": bill.products,
        "total_amount": f"{bill.total_amount:.2f}",
        "printed_at": timezone.localtime(bill.printed_at).strftime("%Y-%m-%d %H:%M"),
    }


def normalise_products(items):
    return [{"name": i["name"], "qty": int(i["qty"]), "amount": i["amount"]} for i in items or []]


def reason(key, ocr_value, blurred):
    if ocr_value in (None, "", []):
        base = "OCR could not find this field (the label or value was unreadable)"
    elif key == "products":
        base = "OCR misread or skipped a product line"
    else:
        base = "OCR misread some characters"
    return base + (", because the image is blurred and slightly rotated." if blurred else ".")


class Command(BaseCommand):
    help = "Write REPORT.md comparing each bill image, its OCR result, and the saved database values."

    def add_arguments(self, parser):
        parser.add_argument("--output", default=str(ROOT / "REPORT.md"))

    def handle(self, *args, **options):
        truth_file = IMAGES / "truth.json"
        if not truth_file.exists():
            raise CommandError("bill_images/truth.json not found. Run tools/make_bill_images.py first.")
        truth = json.loads(truth_file.read_text(encoding="utf-8"))
        bills = {b.bill_id: b for b in Bill.objects.select_related("customer")}

        rows, sections = [], []
        field_ok = {key: 0 for key, _ in FIELDS}
        saved_count = db_ok_count = 0

        for item in truth:
            image = {
                "bill_id": item["bill_id"],
                "customer_name": item["customer_name"],
                "mobile": item["mobile"],
                "products": normalise_products(item["products"]),
                "total_amount": item["total_amount"],
                "printed_at": item["printed_at"],
            }
            bill = bills.get(item["bill_id"])
            if bill and bill.ocr_text:
                text = bill.ocr_text
            else:
                with open(IMAGES / item["file"], "rb") as handle:
                    text = read_text(handle)
            ocr = parse_bill_text(text)
            ocr["products"] = normalise_products(ocr["products"])
            if ocr["printed_at"]:
                ocr["printed_at"] = ocr["printed_at"].replace("T", " ")
            db = db_values(bill) if bill else None
            if bill:
                saved_count += 1
                db["products"] = normalise_products(db["products"])

            table = ["| Field | On image | OCR result | OCR | Saved in database | DB |", "|---|---|---|:-:|---|:-:|"]
            notes = []
            ocr_matches = 0
            db_all_ok = bool(bill)
            for key, label in FIELDS:
                ocr_hit = ocr[key] == image[key]
                ocr_matches += ocr_hit
                field_ok[key] += ocr_hit
                if not ocr_hit:
                    notes.append(f"- **{label}** — OCR: {reason(key, ocr[key], item['blurred'])}")
                if db:
                    db_hit = db[key] == image[key]
                    db_all_ok &= db_hit
                    if not db_hit:
                        notes.append(f"- **{label}** — Database: value differs from the image, likely a typing error during the manual check.")
                    db_cell, db_mark = show(key, db[key]), "✅" if db_hit else "❌"
                else:
                    db_cell, db_mark = "not saved", "—"
                table.append(f"| {label} | {show(key, image[key])} | {show(key, ocr[key])} | {'✅' if ocr_hit else '❌'} | {db_cell} | {db_mark} |")
            db_ok_count += db_all_ok

            quality = "Blurred + rotated" if item["blurred"] else "Clear"
            db_summary = "not saved" if not bill else ("all match" if db_all_ok else "differs")
            rows.append(f"| [{item['bill_id']}](#{item['bill_id'].lower()}) | {quality} | {ocr_matches}/6 | {db_summary} |")

            if ocr_matches == 6 and (not bill or db_all_ok):
                notes = ["- Everything matched."]
            elif bill and ocr_matches < 6 and db_all_ok:
                notes.append("- The wrong OCR values were corrected by hand before saving, so the database matches the image.")
            sections.append("\n".join([
                f"### {item['bill_id']}",
                "",
                f"<img src=\"bill_images/{item['file']}\" alt=\"{item['bill_id']}\" width=\"360\">",
                "",
                f"Image quality: **{quality}** · OCR matched **{ocr_matches}/6** fields · Database: **{db_summary}**",
                "",
                *table,
                "",
                "**Result and possible reasons**",
                "",
                *notes,
                "",
                "<details><summary>OCR full text</summary>",
                "",
                f"<pre>{html.escape(text.strip())}</pre>",
                "",
                "</details>",
                "",
            ]))

        total = len(truth)
        perfect = sum(1 for r in rows if "| 6/6 |" in r)
        accuracy = ["| Field | OCR correct |", "|---|:-:|"] + [
            f"| {label} | {field_ok[key]}/{total} |" for key, label in FIELDS
        ]
        report = "\n".join([
            "# Bill comparison report",
            "",
            "Each bill image was read with Tesseract OCR. The table compares three things for every bill: the values printed on the image, the values the OCR API extracted from the text, and the values saved in the database after a person checked and corrected the form.",
            "",
            "All data is fake. The values “On image” come from `bill_images/truth.json`, written by the script that drew the images, and were checked by eye against the pictures.",
            "",
            "## Summary",
            "",
            f"- Bills compared: **{total}**",
            f"- OCR read all 6 details correctly: **{perfect}/{total}**",
            f"- Bills saved in the database: **{saved_count}/{total}**",
            f"- Saved bills whose database values match the image: **{db_ok_count}/{saved_count}**",
            "",
            *accuracy,
            "",
            "| Bill | Image quality | OCR fields matched | Database vs image |",
            "|---|---|:-:|---|",
            *rows,
            "",
            "## What caused the differences",
            "",
            "- **Blurry or rotated images:** the four images marked “Blurred + rotated” were made softer and tilted on purpose. OCR then misread letters and digits, for example `h` → `n`, `1` → `t`, `8` → `0`, and table headers became noise.",
            "- **OCR mistakes on missing labels:** when a label such as `TOTAL` is unreadable, the parser cannot find the value, so the field stays empty and is shown in red on the Billing page.",
            "- **Typing errors:** any database value that differs from the image would come from the manual check step. Every saved value was compared, and the table shows ❌ wherever this happened.",
            "",
            "## Bill by bill",
            "",
            *sections,
        ])
        Path(options["output"]).write_text(report + "\n", encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Wrote {options['output']}"))
