import json
import random
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "bill_images"
FIXTURE = ROOT / "crm" / "registration" / "fixtures" / "demo_customers.json"

CUSTOMERS = [
    ("Rahim Uddin", "1990-03-14"),
    ("Karim Hossain", "1985-07-22"),
    ("Nusrat Jahan", "1994-11-02"),
    ("Farhana Akter", "1992-01-30"),
    ("Tanvir Ahmed", "1988-05-17"),
    ("Sadia Islam", "1996-09-09"),
    ("Imran Kabir", "1983-12-25"),
    ("Mitu Rahman", "1999-04-11"),
    ("Arif Chowdhury", "1991-08-03"),
    ("Lamia Sultana", "1997-02-19"),
]

PRODUCTS = [
    ("Basmati Rice 5kg", Decimal("900.00")),
    ("Soybean Oil 1L", Decimal("190.00")),
    ("Red Lentils 1kg", Decimal("140.00")),
    ("White Sugar 1kg", Decimal("130.00")),
    ("Fresh Milk 1L", Decimal("95.00")),
    ("Brown Bread", Decimal("70.00")),
    ("Eggs 12pcs", Decimal("150.00")),
    ("Green Tea 100g", Decimal("220.00")),
    ("Bath Soap", Decimal("60.00")),
    ("Toothpaste 150g", Decimal("120.00")),
    ("Potato 2kg", Decimal("80.00")),
    ("Onion 1kg", Decimal("110.00")),
    ("Chicken 1kg", Decimal("320.00")),
    ("Instant Noodles", Decimal("25.00")),
    ("Mineral Water 2L", Decimal("40.00")),
]

BLURRED = {5, 10, 15, 20}
WIDTH = 820


def load_font(size, bold=False):
    names = ["arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold else ["arial.ttf", "DejaVuSans.ttf"]
    for name in names:
        for folder in ("", "C:/Windows/Fonts/", "/usr/share/fonts/truetype/dejavu/", "/Library/Fonts/"):
            try:
                return ImageFont.truetype(folder + name, size)
            except OSError:
                continue
    return ImageFont.load_default(size=size)


def mobile_for(index):
    return f"0100000{index + 1:04d}"


def email_for(name):
    return name.lower().replace(" ", ".") + "@example.com"


def build_customers():
    return [
        {"name": name, "email": email_for(name), "mobile": mobile_for(i), "date_of_birth": dob}
        for i, (name, dob) in enumerate(CUSTOMERS)
    ]


def build_bills(customers, rng):
    start = datetime(2026, 10, 1, 9, 0)
    bills = []
    for n in range(1, 21):
        customer = customers[(n - 1) % len(customers)]
        items = []
        for name, unit in rng.sample(PRODUCTS, rng.randint(2, 5)):
            qty = rng.randint(1, 4)
            items.append({"name": name, "qty": qty, "amount": f"{unit * qty:.2f}"})
        total = sum(Decimal(i["amount"]) for i in items)
        printed = start + timedelta(days=(n - 1) * 2, hours=rng.randint(0, 10), minutes=rng.randint(0, 59))
        bills.append({
            "file": f"B-{1000 + n}.png",
            "bill_id": f"B-{1000 + n}",
            "customer_name": customer["name"],
            "mobile": customer["mobile"],
            "products": items,
            "total_amount": f"{total:.2f}",
            "printed_at": printed.strftime("%Y-%m-%d %H:%M"),
            "blurred": n in BLURRED,
        })
    return bills


def draw_bill(bill):
    title = load_font(34, bold=True)
    body = load_font(26)
    strong = load_font(28, bold=True)
    height = 560 + 44 * len(bill["products"])
    img = Image.new("RGB", (WIDTH, height), "white")
    d = ImageDraw.Draw(img)
    left, right, qty_x = 50, WIDTH - 50, WIDTH - 260

    def center(text, y, font):
        w = d.textlength(text, font=font)
        d.text(((WIDTH - w) / 2, y), text, fill="black", font=font)

    def rtext(text, x, y, font):
        d.text((x - d.textlength(text, font=font), y), text, fill="black", font=font)

    def rule(y):
        d.line((left, y, right, y), fill="black", width=2)

    center("DEMO MART", 30, title)
    center("12 Sample Road, Test City", 76, body)
    rule(124)
    date_text, time_text = bill["printed_at"].split(" ")
    y = 144
    for line in (
        f"Bill ID: {bill['bill_id']}",
        f"Date: {date_text}    Time: {time_text}",
        f"Customer: {bill['customer_name']}",
        f"Mobile: {bill['mobile']}",
    ):
        d.text((left, y), line, fill="black", font=body)
        y += 44
    rule(y + 6)
    y += 24
    d.text((left, y), "Item", fill="black", font=strong)
    rtext("Qty", qty_x, y, strong)
    rtext("Amount", right, y, strong)
    y += 50
    for item in bill["products"]:
        d.text((left, y), item["name"], fill="black", font=body)
        rtext(str(item["qty"]), qty_x, y, body)
        rtext(item["amount"], right, y, body)
        y += 44
    rule(y + 6)
    y += 24
    d.text((left, y), "TOTAL", fill="black", font=strong)
    rtext(bill["total_amount"], right, y, strong)
    rule(y + 56)
    center("Thank you for shopping!", y + 76, body)

    if bill["blurred"]:
        img = img.rotate(1.2, expand=True, fillcolor="white").filter(ImageFilter.GaussianBlur(1.6))
    return img


def main():
    rng = random.Random(2026)
    customers = build_customers()
    bills = build_bills(customers, rng)
    OUT_DIR.mkdir(exist_ok=True)
    for bill in bills:
        draw_bill(bill).save(OUT_DIR / bill["file"])
    (OUT_DIR / "truth.json").write_text(json.dumps(bills, indent=2), encoding="utf-8")
    fixture = [
        {"model": "registration.registration", "pk": i + 1, "fields": c}
        for i, c in enumerate(customers)
    ]
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(fixture, indent=2), encoding="utf-8")
    print(f"Wrote {len(bills)} images to {OUT_DIR}")


if __name__ == "__main__":
    main()
