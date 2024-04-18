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
)

app_name = "billing"

urlpatterns = [
    path("", BillingIndexView.as_view(), name="billing-index"),
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
]
