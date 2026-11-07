from django.test import SimpleTestCase

from registration.ocr import parse_bill_text

CLEAN = """DEMO MART
12 Sample Road, Test City
Bill ID: B-1001
Date: 2026-10-01 Time: 18:39
Customer: Rahim Uddin
Mobile: 01000000001
Item Qty Amount
Brown Bread 1 70.00
Bath Soap 2 120.00
TOTAL 190.00
Thank you for shopping!
"""

NOISY = """DEMO MART
a OeSe
Bill 1D: B-1O10
Date: 2026-10-19 Time: 17:42
Customer: Lamia Sultana
Mobile: 0100000OO10
es
Chicken tkg 3 900.00
White Sugar 1kg 4 520.00
et
TOTAL 1,420.00
"""


class ParseBillTextTests(SimpleTestCase):
    def test_clean_text_gives_all_six_fields(self):
        result = parse_bill_text(CLEAN)
        self.assertEqual(result["bill_id"], "B-1001")
        self.assertEqual(result["customer_name"], "Rahim Uddin")
        self.assertEqual(result["mobile"], "01000000001")
        self.assertEqual(result["printed_at"], "2026-10-01T18:39")
        self.assertEqual(result["total_amount"], "190.00")
        self.assertEqual(result["products"], [
            {"name": "Brown Bread", "qty": 1, "amount": "70.00"},
            {"name": "Bath Soap", "qty": 2, "amount": "120.00"},
        ])

    def test_noisy_text_fixes_common_digit_mistakes(self):
        result = parse_bill_text(NOISY)
        self.assertEqual(result["bill_id"], "B-1010")
        self.assertEqual(result["mobile"], "01000000010")
        self.assertEqual(result["total_amount"], "1420.00")
        self.assertEqual(len(result["products"]), 2)

    def test_missing_fields_are_none(self):
        result = parse_bill_text("nothing useful here")
        self.assertIsNone(result["bill_id"])
        self.assertIsNone(result["customer_name"])
        self.assertIsNone(result["mobile"])
        self.assertIsNone(result["total_amount"])
        self.assertIsNone(result["printed_at"])
        self.assertEqual(result["products"], [])
