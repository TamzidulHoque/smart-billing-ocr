from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.urls import reverse
from PIL import Image, UnidentifiedImageError
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Bill, Registration

ALLOWED_IMAGE_FORMATS = {"PNG", "JPEG"}
MAX_IMAGE_PIXELS = 25_000_000


def validate_bill_image(file):
    if file.size > settings.MAX_BILL_IMAGE_BYTES:
        raise serializers.ValidationError("Image must be 5 MB or smaller.")
    try:
        file.seek(0)
        with Image.open(file) as image:
            image_format = image.format
            width, height = image.size
            image.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise serializers.ValidationError("Upload a valid PNG or JPEG image.")
    finally:
        file.seek(0)
    if image_format not in ALLOWED_IMAGE_FORMATS:
        raise serializers.ValidationError("Only PNG and JPEG images are allowed.")
    if width * height > MAX_IMAGE_PIXELS:
        raise serializers.ValidationError("Image dimensions are too large.")
    return file


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, data):
        user = get_user_model().objects.filter(email__iexact=data["email"]).first()
        if user is not None:
            user = authenticate(username=user.get_username(), password=data["password"])
        if user is None or not user.is_active:
            raise serializers.ValidationError("Invalid email or password.")
        refresh = RefreshToken.for_user(user)
        return {"refresh": str(refresh), "access": str(refresh.access_token)}


class RegistrationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Registration
        fields = ["id", "name", "email", "mobile", "date_of_birth"]

    def validate_name(self, value):
        value = " ".join(value.split())
        if not value:
            raise serializers.ValidationError("Name is required.")
        return value


class OcrUploadSerializer(serializers.Serializer):
    image = serializers.ImageField()

    def validate_image(self, value):
        return validate_bill_image(value)


class ProductSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    qty = serializers.IntegerField(min_value=1, max_value=9999)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0)


class BillSerializer(serializers.ModelSerializer):
    customer = serializers.PrimaryKeyRelatedField(queryset=Registration.objects.all())
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_mobile = serializers.CharField(source="customer.mobile", read_only=True)
    products = serializers.JSONField()
    bill_image = serializers.ImageField(write_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Bill
        fields = [
            "id",
            "bill_id",
            "customer",
            "customer_name",
            "customer_mobile",
            "products",
            "total_amount",
            "printed_at",
            "bill_image",
            "image_url",
            "ocr_text",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_image_url(self, obj):
        return reverse("bill-image", kwargs={"bill_id": obj.bill_id})

    def validate_bill_id(self, value):
        return value.strip().upper()

    def validate_bill_image(self, value):
        return validate_bill_image(value)

    def validate_products(self, value):
        if not isinstance(value, list) or not value:
            raise serializers.ValidationError("Add at least one product.")
        items = ProductSerializer(data=value, many=True)
        if not items.is_valid():
            raise serializers.ValidationError(items.errors)
        return [
            {"name": " ".join(i["name"].split()), "qty": i["qty"], "amount": f"{i['amount']:.2f}"}
            for i in items.validated_data
        ]
