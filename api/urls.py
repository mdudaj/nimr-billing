from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BillCntrNumPaymentCallback,
    BillCntrNumResponseCallback,
    BillSubmissionView,
    InternalBillDeliveriesResendView,
    InternalBillDeliveriesView,
)

router = DefaultRouter()

app_name = "api"

urlpatterns = [
    path("", include(router.urls)),
    path(
        "bill-submission/",
        BillSubmissionView.as_view({"post": "create"}),
        name="bill-submission",
    ),
    path(
        "bill-cntrl-num-response-callback/",
        BillCntrNumResponseCallback.as_view(),
        name="bill-cntrl-num-response-callback",
    ),
    path(
        "bill-cntrl-num-payment-callback/",
        BillCntrNumPaymentCallback.as_view(),
        name="bill-cntrl-num-payment-callback",
    ),
    path(
        "internal/billing/bills/<str:bill_id>/deliveries",
        InternalBillDeliveriesView.as_view(),
        name="internal-bill-deliveries",
    ),
    path(
        "internal/billing/bills/<str:bill_id>/deliveries/resend",
        InternalBillDeliveriesResendView.as_view(),
        name="internal-bill-deliveries-resend",
    ),
]
