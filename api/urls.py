from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CustomerViewSet, BillViewSet


router = DefaultRouter()

app_name = "api"

urlpatterns = [
    path("", include(router.urls)),
    path(
        "bill/submission/",
        BillViewSet.as_view({"post": "create"}),
        name="bill-submission",
    ),
]
