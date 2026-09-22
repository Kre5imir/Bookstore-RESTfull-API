import logging
import re
import time
import uuid

from bookstore import metrics

logger = logging.getLogger("bookstore.access")
_REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{1,64}")


class RequestTrackingMiddleware:
    """Assign a request id, log the completed request, and update metrics."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get("X-Request-ID", "")
        if not _REQUEST_ID.fullmatch(request_id):
            request_id = uuid.uuid4().hex
        request.request_id = request_id
        started = time.perf_counter()
        status = 500
        try:
            response = self.get_response(request)
            status = response.status_code
        except Exception:
            self._finish(request, request_id, status, started)
            raise
        response["X-Request-ID"] = request_id
        self._finish(request, request_id, status, started)
        return response

    def _finish(self, request, request_id, status, started):
        duration_ms = (time.perf_counter() - started) * 1000
        route = _route(request)
        metrics.record(request.method, route, status, duration_ms)
        logger.info(
            "request method=%s path=%s route=%s status=%s duration_ms=%.2f request_id=%s",
            request.method,
            request.path,
            route,
            status,
            duration_ms,
            request_id,
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.path,
                "route": route,
                "status": status,
                "duration_ms": round(duration_ms, 3),
                "remote_addr": request.META.get("REMOTE_ADDR", ""),
            },
        )


def _route(request):
    match = getattr(request, "resolver_match", None)
    if match is not None and match.route:
        return "/" + match.route.lstrip("/")
    return request.path
