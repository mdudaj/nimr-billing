from django.urls import path

from .views import (
    BillingIndexView,
    CustomerListView,
    CustomerDetailView,
    CustomerCreateView,
    CustomerUpdateView,
    CustomerDeleteView,
    ServiceProviderListView,
    ServiceProviderDetailView,
    ServiceProviderCreateView,
    ServiceProviderUpdateView,
    ServiceProviderDeleteView,
    RevenueSourceListView,
    RevenueSourceDetailView,
    RevenueSourceCreateView,
    RevenueSourceUpdateView,
    RevenueSourceDeleteView,
    BillListView,
    BillDetailView,
    BillCreateView,
    BillUpdateView,
    BillDeleteView,
    BillControlNumberResponseCallbackView,
    BillControlNumberPaymentCallbackView,
    BillControlNumberReconciliationCallbackView,
    BillCancellationListView,
    BillCancellationDetailView,
    BillCancellationCreateView,
    BillCancellationUpdateView,
    BillCancellationDeleteView,
    SystemInfoListView,
    SystemInfoDetailView,
    SystemInfoCreateView,
    SystemInfoUpdateView,
    SystemInfoDeleteView,
    PaymentListView,
    PaymentDetailView,
    check_control_number_request_status,
    generate_bill_print_pdf,
    BillPrintPDFView,
    BillTransferPrintPDFView,
    BillReceiptPrintPDFView,
)

app_name = "billing"

urlpatterns = [
    path("", BillingIndexView.as_view(), name="billing-index"),
    path(
        "system-info/",
        SystemInfoListView.as_view(),
        name="system-info-list",
    ),
    path(
        "system-info/<int:pk>/",
        SystemInfoDetailView.as_view(),
        name="system-info-detail",
    ),
    path(
        "system-info/create/",
        SystemInfoCreateView.as_view(),
        name="system-info-create",
    ),
    path(
        "system-info/<int:pk>/update/",
        SystemInfoUpdateView.as_view(),
        name="system-info-update",
    ),
    path(
        "system-info/<int:pk>/delete/",
        SystemInfoDeleteView.as_view(),
        name="system-info-delete",
    ),
    path("customer/", CustomerListView.as_view(), name="customer-list"),
    path("customer/<int:pk>/", CustomerDetailView.as_view(), name="customer-detail"),
    path("customer/create/", CustomerCreateView.as_view(), name="customer-create"),
    path(
        "customer/<int:pk>/update/",
        CustomerUpdateView.as_view(),
        name="customer-update",
    ),
    path(
        "customer/<int:pk>/delete/",
        CustomerDeleteView.as_view(),
        name="customer-delete",
    ),
    path(
        "service-provider/",
        ServiceProviderListView.as_view(),
        name="sp-list",
    ),
    path(
        "service-provider/<int:pk>/",
        ServiceProviderDetailView.as_view(),
        name="sp-detail",
    ),
    path(
        "service-provider/create/",
        ServiceProviderCreateView.as_view(),
        name="sp-create",
    ),
    path(
        "service-provider/<int:pk>/update/",
        ServiceProviderUpdateView.as_view(),
        name="sp-update",
    ),
    path(
        "service-provider/<int:pk>/delete/",
        ServiceProviderDeleteView.as_view(),
        name="sp-delete",
    ),
    path("revenue-source/", RevenueSourceListView.as_view(), name="rs-list"),
    path(
        "revenue-source/<int:pk>/",
        RevenueSourceDetailView.as_view(),
        name="rs-detail",
    ),
    path(
        "revenue-source/create/",
        RevenueSourceCreateView.as_view(),
        name="rs-create",
    ),
    path(
        "revenue-source/<int:pk>/update/",
        RevenueSourceUpdateView.as_view(),
        name="rs-update",
    ),
    path(
        "revenue-source/<int:pk>/delete/",
        RevenueSourceDeleteView.as_view(),
        name="rs-delete",
    ),
    path("bill/", BillListView.as_view(), name="bill-list"),
    path("bill/<int:pk>/", BillDetailView.as_view(), name="bill-detail"),
    path("bill/create/", BillCreateView.as_view(), name="bill-create"),
    path("bill/<int:pk>/update/", BillUpdateView.as_view(), name="bill-update"),
    path("bill/<int:pk>/delete/", BillDeleteView.as_view(), name="bill-delete"),
    path("bill/print/<int:pk>/", BillPrintPDFView.as_view(), name="bill-print"),
    path(
        "bill/transfer-print/<int:pk>/",
        BillTransferPrintPDFView.as_view(),
        name="bill-transfer-print",
    ),
    path(
        "bill/receipt-print/<int:pk>/",
        BillReceiptPrintPDFView.as_view(),
        name="bill-receipt-print",
    ),
    path(
        "bill-control-number-response-callback/",
        BillControlNumberResponseCallbackView.as_view(),
        name="bill-control-number-response-callback",
    ),
    path(
        "bill-control-number-payment-callback/",
        BillControlNumberPaymentCallbackView.as_view(),
        name="bill-control-number-payment-callback",
    ),
    path(
        "bill-control-number-reconciliation-callback/",
        BillControlNumberReconciliationCallbackView.as_view(),
        name="bill-control-number-reconciliation-callback",
    ),
    path("payment/", PaymentListView.as_view(), name="payment-list"),
    path("payment/<int:pk>/", PaymentDetailView.as_view(), name="payment-detail"),
    path(
        "check-control-number-request-status/<int:pk>/",
        check_control_number_request_status,
        name="check-control-number-request-status",
    ),
    path(
        "generate-bill-pdf/<int:pk>/",
        generate_bill_print_pdf,
        name="generate-bill-print-pdf",
    ),
    path(
        "cancelled-bill/",
        BillCancellationListView.as_view(),
        name="cancelled-bill-list",
    ),
    path(
        "cancelled-bill/<int:pk>/",
        BillCancellationDetailView.as_view(),
        name="cancelled-bill-detail",
    ),
    path(
        "cancelled-bill/create/",
        BillCancellationCreateView.as_view(),
        name="cancelled-bill-create",
    ),
    path(
        "cancelled-bill/<int:pk>/update/",
        BillCancellationUpdateView.as_view(),
        name="cancelled-bill-update",
    ),
    path(
        "cancelled-bill/<int:pk>/delete/",
        BillCancellationDeleteView.as_view(),
        name="cancelled-bill-delete",
    ),
]
