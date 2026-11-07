from django.contrib import admin

from .models import Bill, Registration


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "mobile", "date_of_birth"]
    search_fields = ["name", "email", "mobile"]


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ["bill_id", "customer", "total_amount", "printed_at", "created_at"]
    search_fields = ["bill_id", "customer__name"]
    list_filter = ["printed_at"]
