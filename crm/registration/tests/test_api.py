import io
import json
import shutil
import tempfile
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase

from registration.models import Bill, Registration
from registration.ocr import OcrUnavailable

MEDIA = tempfile.mkdtemp()


def png_file(name="bill.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (60, 40), "white").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


OCR_TEXT = """Bill ID: B-1001
Date: 2026-10-01 Time: 18:39
Customer: Rahim Uddin
Mobile: 01000000001
Item Qty Amount
Brown Bread 1 70.00
TOTAL 70.00
"""


@override_settings(MEDIA_ROOT=MEDIA)
class ApiTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        get_user_model().objects.create_user("staff", "staff@example.com", "Str0ng-pass-123")
        self.rahim = Registration.objects.create(name="Rahim Uddin", email="rahim@example.com", mobile="01000000001")
        self.karim = Registration.objects.create(name="Karim Hossain", email="karim@example.com", mobile="01000000002")

    def login(self):
        response = self.client.post("/account/api/login/", {"email": "staff@example.com", "password": "Str0ng-pass-123"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        return response.data

    def create_bill(self, bill_id="B-1001", customer=None, printed_at="2026-10-01T18:39", total="70.00"):
        return self.client.post("/account/api/bills/", {
            "bill_id": bill_id,
            "customer": (customer or self.rahim).id,
            "products": json.dumps([{"name": "Brown Bread", "qty": 1, "amount": total}]),
            "total_amount": total,
            "printed_at": printed_at,
            "ocr_text": "raw text",
            "bill_image": png_file(),
        }, format="multipart")

    def test_login_returns_tokens_and_rejects_bad_password(self):
        tokens = self.login()
        self.assertIn("refresh", tokens)
        self.client.credentials()
        response = self.client.post("/account/api/login/", {"email": "staff@example.com", "password": "wrong"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_all_apis_need_a_token(self):
        for url in ["/account/api/bills/", "/account/api/bills/B-1001/", "/account/api/registrations/"]:
            self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.client.post("/account/api/ocr/", {"image": png_file()}, format="multipart").status_code, 401)

    def test_registration_create_and_validate_mobile(self):
        self.login()
        ok = self.client.post("/account/api/registrations/", {"name": "Nusrat Jahan", "email": "nusrat@example.com", "mobile": "01000000003"}, format="json")
        self.assertEqual(ok.status_code, 201)
        bad = self.client.post("/account/api/registrations/", {"name": "X", "email": "x@example.com", "mobile": "12345"}, format="json")
        self.assertEqual(bad.status_code, 400)
        self.assertIn("mobile", bad.data)

    @mock.patch("registration.views.read_text", return_value=OCR_TEXT)
    def test_ocr_returns_full_text_fields_and_matched_customer(self, _read):
        self.login()
        response = self.client.post("/account/api/ocr/", {"image": png_file()}, format="multipart")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["full_text"], OCR_TEXT)
        self.assertEqual(response.data["bill_id"], "B-1001")
        self.assertEqual(response.data["total_amount"], "70.00")
        self.assertEqual(response.data["matched_customer"]["id"], self.rahim.id)
        self.assertEqual(response.data["matched_customer"]["matched_by"], "name_and_mobile")

    def test_ocr_rejects_non_image(self):
        self.login()
        fake = SimpleUploadedFile("bill.png", b"not an image", content_type="image/png")
        response = self.client.post("/account/api/ocr/", {"image": fake}, format="multipart")
        self.assertEqual(response.status_code, 400)

    @mock.patch("registration.views.read_text", side_effect=OcrUnavailable("missing"))
    def test_ocr_reports_missing_engine(self, _read):
        self.login()
        response = self.client.post("/account/api/ocr/", {"image": png_file()}, format="multipart")
        self.assertEqual(response.status_code, 503)

    def test_save_bill_and_get_it_by_printed_bill_id(self):
        self.login()
        created = self.create_bill()
        self.assertEqual(created.status_code, 201, created.data)
        bill = Bill.objects.get(bill_id="B-1001")
        response = self.client.get("/account/api/bills/B-1001/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], bill.id)
        self.assertEqual(response.data["customer_name"], "Rahim Uddin")
        self.assertEqual(response.data["products"], [{"name": "Brown Bread", "qty": 1, "amount": "70.00"}])
        self.assertEqual(self.client.get(f"/account/api/bills/{bill.id}/").status_code, 404)
        self.assertEqual(self.client.get("/account/api/bills/B-9999/").status_code, 404)

    def test_duplicate_bill_id_and_bad_products_are_rejected(self):
        self.login()
        self.create_bill()
        self.assertEqual(self.create_bill().status_code, 400)
        response = self.client.post("/account/api/bills/", {
            "bill_id": "B-2000", "customer": self.rahim.id, "products": json.dumps([{"name": "", "qty": 0, "amount": "-1"}]),
            "total_amount": "10.00", "printed_at": "2026-10-01T10:00", "bill_image": png_file(),
        }, format="multipart")
        self.assertEqual(response.status_code, 400)
        self.assertIn("products", response.data)

    def test_bill_image_is_served_only_with_token(self):
        self.login()
        self.create_bill()
        response = self.client.get("/account/api/bills/B-1001/image/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.client.credentials()
        self.assertEqual(self.client.get("/account/api/bills/B-1001/image/").status_code, 401)

    def test_search_filter_ordering_and_pages(self):
        self.login()
        self.create_bill("B-1001", self.rahim, "2026-10-01T10:00", "70.00")
        self.create_bill("B-1002", self.karim, "2026-10-05T10:00", "150.00")
        self.create_bill("B-1003", self.karim, "2026-10-09T10:00", "90.00")

        def ids(query):
            response = self.client.get(f"/account/api/bills/{query}")
            self.assertEqual(response.status_code, 200)
            return [b["bill_id"] for b in response.data["results"]]

        self.assertEqual(ids("?search=B-1002"), ["B-1002"])
        self.assertEqual(sorted(ids("?search=karim")), ["B-1002", "B-1003"])
        self.assertEqual(ids(f"?customer={self.rahim.id}"), ["B-1001"])
        self.assertEqual(ids("?printed_from=2026-10-05&printed_to=2026-10-05"), ["B-1002"])
        self.assertEqual(ids("?ordering=total_amount"), ["B-1001", "B-1003", "B-1002"])
        page = self.client.get("/account/api/bills/?page_size=2&page=2&ordering=bill_id")
        self.assertEqual(page.data["count"], 3)
        self.assertEqual([b["bill_id"] for b in page.data["results"]], ["B-1003"])
        self.assertEqual(self.client.get("/account/api/bills/?printed_from=not-a-date").status_code, 400)
