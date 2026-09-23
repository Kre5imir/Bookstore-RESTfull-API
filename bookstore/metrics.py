import threading
import time

_lock = threading.Lock()
_started = time.monotonic()
_requests = {}
_duration_sum = {}
_duration_count = {}


def record(method, route, status, duration_ms):
    request_key = (method, route, str(status))
    duration_key = (method, route)
    with _lock:
        _requests[request_key] = _requests.get(request_key, 0) + 1
        _duration_sum[duration_key] = _duration_sum.get(duration_key, 0.0) + float(duration_ms)
        _duration_count[duration_key] = _duration_count.get(duration_key, 0) + 1


def uptime_seconds():
    return time.monotonic() - _started


def render():
    lines = [
        "# HELP bookstore_uptime_seconds Seconds since the API process started.",
        "# TYPE bookstore_uptime_seconds gauge",
        f"bookstore_uptime_seconds {uptime_seconds():.3f}",
        "# HELP bookstore_http_requests_total HTTP requests processed, labeled by method, route, and status.",
        "# TYPE bookstore_http_requests_total counter",
    ]
    with _lock:
        request_items = sorted(_requests.items())
        duration_items = sorted(_duration_sum.items())
        duration_counts = dict(_duration_count)
    for (method, route, status), count in request_items:
        lines.append(
            "bookstore_http_requests_total{"
            f'method="{_escape(method)}",route="{_escape(route)}",status="{_escape(status)}"'
            f"}} {count}"
        )
    lines.extend(
        [
            "# HELP bookstore_http_request_duration_ms_sum Total request duration in milliseconds.",
            "# TYPE bookstore_http_request_duration_ms_sum counter",
        ]
    )
    for (method, route), total in duration_items:
        lines.append(
            "bookstore_http_request_duration_ms_sum{"
            f'method="{_escape(method)}",route="{_escape(route)}"'
            f"}} {total:.3f}"
        )
    lines.extend(
        [
            "# HELP bookstore_http_request_duration_ms_count Observed request count for duration totals.",
            "# TYPE bookstore_http_request_duration_ms_count counter",
        ]
    )
    for (method, route), total in duration_items:
        lines.append(
            "bookstore_http_request_duration_ms_count{"
            f'method="{_escape(method)}",route="{_escape(route)}"'
            f"}} {duration_counts[(method, route)]}"
        )
    return "\n".join(lines) + "\n"


def _escape(value):
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
