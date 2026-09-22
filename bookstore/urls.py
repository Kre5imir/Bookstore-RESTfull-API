"""URL configuration for the Readify Bookstore API."""

from django.contrib import admin
from django.urls import include, path

from bookstore import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.api_root, name="api-root"),
    path("health", views.health, name="health"),
    path("metrics", views.metrics_view, name="metrics"),
    path("openapi.yaml", views.openapi_yaml, name="openapi"),
    path("", include("books.urls")),
    path("<path:unmatched>", views.not_found, name="not-found"),
]

handler500 = "bookstore.views.server_error"
