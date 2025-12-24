from django.contrib import admin
from django.urls import include, path
from core.health import health_check

urlpatterns = [
    # path('', include('home.urls')),
    # path("admin/", admin.site.urls),
    # path("", include('admin_berry.urls')),
    path("", include("accounts.urls")),
    path("", include("billing.urls")),
    path("api/", include("api.urls")),
    path("health/", health_check, name="health_check"),
]
