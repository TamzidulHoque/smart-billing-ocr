import json
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError

from registration.models import Bill, Registration
from registration.ocr import parse_bill_text, read_text
from registration.serializers import BillSerializer

IMAGES = settings.BASE_DIR.parent / "bill_images"


class Command(BaseCommand):

    def handle(self, *args, **options):
        truth_file = IMAGES / "truth.json"
        if not truth_file.exists():
            raise CommandError("bill_images/truth.json not found. Run tools/make_bill_images.py first.")
        saved = skipped = 0
        for item in json.loads(truth_file.read_text(encoding="utf-8")):
            if Bill.objects.filter(bill_id=item["bill_id"]).exists():
                skipped += 1
                continue
            path = Path(IMAGES / item["file"])
            data = path.read_bytes()
            upload = SimpleUploadedFile(path.name, data, content_type="image/png")
            text = read_text(upload)
            ocr = parse_bill_text(text)
            customer = Registration.objects.get(mobile=item["mobile"])
            serializer = BillSerializer(data={
                "bill_id": item["bill_id"],
                "customer": customer.id,
                "products": item["products"],
                "total_amount": item["total_amount"],
                "printed_at": item["printed_at"].replace(" ", "T"),
                "ocr_text": text,
                "bill_image": SimpleUploadedFile(path.name, data, content_type="image/png"),
            })
            serializer.is_valid(raise_exception=True)
            serializer.save()
            fixed = [k for k in ("bill_id", "customer_name", "mobile", "total_amount") if ocr[k] != item[k]]
            if ocr["products"] != item["products"]:
                fixed.append("products")
            if ocr["printed_at"] != item["printed_at"].replace(" ", "T"):
                fixed.append("printed_at")
            note = f" (corrected: {', '.join(fixed)})" if fixed else ""
            self.stdout.write(f"Saved {item['bill_id']}{note}")
            saved += 1
        self.stdout.write(self.style.SUCCESS(f"Saved {saved} bills, skipped {skipped} already saved."))
