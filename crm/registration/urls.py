from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

router = DefaultRouter()
router.register("registrations", views.RegistrationViewSet, basename="registration")
router.register("bills", views.BillViewSet, basename="bill")

urlpatterns = [
    path("login/", views.Page.as_view(template_name="login.html"), name="login"),
    path("customers/", views.Page.as_view(template_name="customers.html"), name="customers"),
    path("billing/", views.Page.as_view(template_name="billing.html"), name="billing"),
    path("bills/", views.Page.as_view(template_name="bills.html"), name="bills"),
    path("bills/<str:bill_id>/", views.Page.as_view(template_name="bill_detail.html"), name="bill_detail"),
    path("api/login/", views.LoginAPIView.as_view(), name="api_login"),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/ocr/", views.OcrAPIView.as_view(), name="api_ocr"),
    path("api/", include(router.urls)),
]
