from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    BillSubmissionView,
    BillCntrNumResponseCallback,
    BillCntrNumPaymentCallback,
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
]
