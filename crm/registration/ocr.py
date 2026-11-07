import os
import re
import shutil
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pytesseract
from django.conf import settings
from PIL import Image, ImageOps

WINDOWS_TESSERACT = [
    Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
    Path(os.environ.get("LOCALAPPDATA", "C:/")) / "Programs" / "Tesseract-OCR" / "tesseract.exe",
]
DIGIT_FIXES = str.maketrans({"O": "0", "o": "0", "D": "0", "l": "1", "I": "1", "|": "1", "S": "5", "s": "5", "B": "8"})

BILL_ID_RE = re.compile(r"Bill\s*[I1l|][Dd0O]\s*[:;.\-]?\s*([A-Z8]\s*[-–—]\s*[\dOolIS]{3,10})", re.IGNORECASE)
DATE_RE = re.compile(r"Date\s*[:;.\-]?\s*(\d{4})\s*[-/.]\s*(\d{2})\s*[-/.]\s*(\d{2})", re.IGNORECASE)
TIME_RE = re.compile(r"Time\s*[:;.\-]?\s*(\d{1,2})\s*[:.;]\s*(\d{2})", re.IGNORECASE)
CUSTOMER_RE = re.compile(r"Customer(?:\s*Name)?\s*[:;.\-]?\s*(.+)", re.IGNORECASE)
MOBILE_RE = re.compile(r"Mobile(?:[ \t]*No\.?)?[ \t]*[:;.\-]?[ \t]*([\dOolIS][\dOolIS \t\-]{10,15})", re.IGNORECASE)
TOTAL_RE = re.compile(r"^\s*TOTAL\b\s*[:;.\-]?\s*(?:Tk\.?)?\s*([\d,.\s]+\d)", re.IGNORECASE)
HEADER_RE = re.compile(r"\bItem\b.*\bQty\b", re.IGNORECASE)
PRODUCT_RE = re.compile(r"^(.*?[A-Za-z].*?)\s+(\d{1,3})\s+([\d,]+[.,]\d{2})\s*$")


class OcrUnavailable(Exception):
    pass


def tesseract_command():
    if settings.TESSERACT_CMD:
        return settings.TESSERACT_CMD
    found = shutil.which("tesseract")
    if found:
        return found
    for candidate in WINDOWS_TESSERACT:
        if candidate.exists():
            return str(candidate)
    raise OcrUnavailable("Tesseract is not installed or TESSERACT_CMD is not set.")


def prepare_image(image):
    image = ImageOps.exif_transpose(image).convert("L")
    if image.width < 1200:
        scale = 1200 / image.width
        image = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
    return ImageOps.autocontrast(image)


def read_text(image_file):
    pytesseract.pytesseract.tesseract_cmd = tesseract_command()
    image_file.seek(0)
    with Image.open(image_file) as image:
        prepared = prepare_image(image)
    image_file.seek(0)
    try:
        return pytesseract.image_to_string(prepared, lang="eng", config="--psm 6")
    except (pytesseract.TesseractNotFoundError, pytesseract.TesseractError) as exc:
        raise OcrUnavailable(str(exc)) from exc


def to_money(text):
    cleaned = re.sub(r"\s", "", text).replace(",", "")
    if cleaned.count(".") > 1:
        head, _, tail = cleaned.rpartition(".")
        cleaned = head.replace(".", "") + "." + tail
    try:
        return f"{Decimal(cleaned):.2f}"
    except InvalidOperation:
        return None


def money_from_product(text):
    text = text.replace(",", ".") if re.search(r",\d{2}$", text) else text.replace(",", "")
    return to_money(text)


def parse_bill_text(text):
    result = {
        "bill_id": None,
        "customer_name": None,
        "mobile": None,
        "products": [],
        "total_amount": None,
        "printed_at": None,
    }

    match = BILL_ID_RE.search(text)
    if match:
        raw = re.sub(r"[\s–—]", "", match.group(1)).replace("-", "")
        prefix, digits = raw[0].upper(), raw[1:].translate(DIGIT_FIXES)
        prefix = "B" if prefix == "8" else prefix
        result["bill_id"] = f"{prefix}-{digits}"

    match = CUSTOMER_RE.search(text)
    if match:
        name = re.sub(r"[^A-Za-z.' \-]", "", match.group(1)).strip(" .-")
        result["customer_name"] = re.sub(r"\s+", " ", name) or None

    match = MOBILE_RE.search(text)
    if match:
        digits = re.sub(r"\D", "", match.group(1).translate(DIGIT_FIXES))
        result["mobile"] = digits or None

    date_match, time_match = DATE_RE.search(text), TIME_RE.search(text)
    if date_match:
        y, m, d = date_match.groups()
        hh, mm = time_match.groups() if time_match else ("00", "00")
        result["printed_at"] = f"{y}-{m}-{d}T{int(hh):02d}:{mm}"

    lines = [line.strip() for line in text.splitlines()]
    in_items = False
    for line in lines:
        if not line:
            continue
        total_match = TOTAL_RE.match(line)
        if total_match:
            result["total_amount"] = to_money(total_match.group(1))
            in_items = False
            continue
        if HEADER_RE.search(line) or MOBILE_RE.search(line):
            in_items = True
            continue
        if in_items:
            product = PRODUCT_RE.match(line)
            if product:
                name, qty, amount = product.groups()
                result["products"].append({
                    "name": re.sub(r"\s+", " ", name).strip(" .-|"),
                    "qty": int(qty),
                    "amount": money_from_product(amount),
                })
    return result
