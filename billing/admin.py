from django.contrib import admin

from .models import BillingEmailDelivery


@admin.register(BillingEmailDelivery)
class BillingEmailDeliveryAdmin(admin.ModelAdmin):
    list_display = (
        "bill",
        "document_type",
        "recipient_email",
        "status",
        "attempt_count",
        "last_attempt_at",
        "sent_at",
        "created_at",
    )
    list_filter = ("document_type", "status")
    search_fields = ("bill__bill_id", "recipient_email", "event_key")
    readonly_fields = (
        "created_at",
        "updated_at",
    )
