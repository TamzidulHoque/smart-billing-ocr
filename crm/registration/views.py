import mimetypes

import django_filters
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.views.generic import TemplateView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import Bill, Registration
from .ocr import OcrUnavailable, parse_bill_text, read_text
from .serializers import (
    BillSerializer,
    LoginSerializer,
    OcrUploadSerializer,
    RegistrationSerializer,
)


class Page(TemplateView):
    pass


class StandardPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class LoginAPIView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)


class RegistrationViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Registration.objects.all()
    serializer_class = RegistrationSerializer
    pagination_class = StandardPagination
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name", "email", "mobile"]
    ordering = ["name"]
    ordering_fields = ["id", "name", "email", "mobile"]


def match_customer(name, mobile):
    candidates = Registration.objects.filter(mobile=mobile) if mobile else Registration.objects.none()
    if name and candidates.filter(name__iexact=name).exists():
        customer, matched_by = candidates.get(name__iexact=name), "name_and_mobile"
    elif candidates.count() == 1:
        customer, matched_by = candidates.get(), "mobile"
    elif name and Registration.objects.filter(name__iexact=name).count() == 1:
        customer, matched_by = Registration.objects.get(name__iexact=name), "name"
    else:
        return None
    return {"id": customer.id, "name": customer.name, "mobile": customer.mobile, "matched_by": matched_by}


class OcrAPIView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = OcrUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            text = read_text(serializer.validated_data["image"])
        except OcrUnavailable:
            return Response(
                {"detail": "OCR engine is not available on the server."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        fields = parse_bill_text(text)
        return Response({
            "full_text": text,
            **fields,
            "matched_customer": match_customer(fields["customer_name"], fields["mobile"]),
        })


class BillFilter(django_filters.FilterSet):
    customer = django_filters.NumberFilter(field_name="customer_id")
    printed_from = django_filters.DateFilter(field_name="printed_at", lookup_expr="date__gte")
    printed_to = django_filters.DateFilter(field_name="printed_at", lookup_expr="date__lte")

    class Meta:
        model = Bill
        fields = ["customer", "printed_from", "printed_to"]


class BillViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Bill.objects.select_related("customer")
    serializer_class = BillSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    pagination_class = StandardPagination
    lookup_field = "bill_id"
    lookup_value_regex = r"[A-Za-z]-\d{1,10}"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = BillFilter
    search_fields = ["bill_id", "customer__name"]
    ordering = ["-printed_at"]
    ordering_fields = ["bill_id", "printed_at", "total_amount", "created_at"]

    def get_object(self):
        bill = get_object_or_404(self.get_queryset(), bill_id=self.kwargs["bill_id"].upper())
        self.check_object_permissions(self.request, bill)
        return bill

    @action(detail=True, methods=["get"], url_path="image", url_name="image")
    def image(self, request, bill_id=None):
        bill = self.get_object()
        content_type = mimetypes.guess_type(bill.bill_image.name)[0] or "application/octet-stream"
        response = FileResponse(bill.bill_image.open("rb"), content_type=content_type)
        response["Cache-Control"] = "private, no-store"
        return response
