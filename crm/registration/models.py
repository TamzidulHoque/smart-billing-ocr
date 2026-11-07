import uuid
from pathlib import Path

from django.core.validators import MinValueValidator, RegexValidator
from django.db import models

mobile_validator = RegexValidator(r"^01\d{9}$", "Mobile must be 11 digits and start with 01.")
bill_id_validator = RegexValidator(r"^B-\d{4,10}$", "Bill ID must look like B-1001.")


def bill_image_path(instance, filename):
    ext = Path(filename).suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg"}:
        ext = ".png"
    return f"bills/{uuid.uuid4().hex}{ext}"


class Registration(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    mobile = models.CharField(max_length=11, unique=True, validators=[mobile_validator])
    date_of_birth = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.mobile})"


class Bill(models.Model):
    bill_id = models.CharField(max_length=20, unique=True, validators=[bill_id_validator])
    customer = models.ForeignKey(Registration, on_delete=models.PROTECT, related_name="bills")
    products = models.JSONField(default=list)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    printed_at = models.DateTimeField()
    bill_image = models.ImageField(upload_to=bill_image_path)
    ocr_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-printed_at"]

    def __str__(self):
        return self.bill_id
