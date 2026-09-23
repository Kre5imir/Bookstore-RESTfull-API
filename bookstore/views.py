import logging
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.http import HttpResponse

from books.exceptions import ApiError
from books.http import api_view, error_response, json_response
from bookstore import metrics

logger = logging.getLogger("bookstore.health")
SPEC_PATH = Path(settings.BASE_DIR) / "openapi" / "openapi.yaml"


@api_view(["GET"])
def api_root(request):
    return json_response(
        {
            "name": "Readify Bookstore API",
            "version": settings.APP_VERSION,
            "documentation": "/openapi.yaml",
            "health": "/health",
            "metrics": "/metrics",
            "resources": {
                "books": "/books",
                "authors": "/authors",
            },
        }
    )


@api_view(["GET"])
def health(request):
    database = "ok"
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        logger.exception("Database health check failed")
        database = "error"
    status = "ok" if database == "ok" else "unavailable"
    return json_response(
        {
            "status": status,
            "version": settings.APP_VERSION,
            "uptime_seconds": round(metrics.uptime_seconds(), 3),
            "checks": {"database": database},
        },
        status=200 if status == "ok" else 503,
    )


@api_view(["GET"])
def metrics_view(request):
    return HttpResponse(
        metrics.render(),
        content_type="text/plain; version=0.0.4; charset=utf-8",
    )


@api_view(["GET"])
def openapi_yaml(request):
    if not SPEC_PATH.is_file():
        raise ApiError(404, "not_found", "OpenAPI specification is not available.")
    return HttpResponse(
        SPEC_PATH.read_text(encoding="utf-8"),
        content_type="application/yaml; charset=utf-8",
    )


@api_view(["GET", "POST", "PUT", "PATCH", "DELETE"])
def not_found(request, unmatched):
    raise ApiError(404, "not_found", "Resource not found.")


def server_error(request):
    logger.exception("Unhandled server error")
    return error_response(500, "internal_error", "An unexpected error occurred.")
