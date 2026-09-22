import json
from functools import wraps

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from books.exceptions import ApiError


def error_body(code, message, details=None):
    payload = {"error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    return payload


def json_response(payload, status=200, headers=None):
    response = JsonResponse(
        payload,
        status=status,
        json_dumps_params={"ensure_ascii": False},
    )
    if headers:
        for key, value in headers.items():
            response[key] = value
    return response


def error_response(status, code, message, details=None):
    return json_response(error_body(code, message, details), status=status)


def empty_response(status, headers=None):
    response = HttpResponse(status=status)
    if headers:
        for key, value in headers.items():
            response[key] = value
    return response


def api_view(methods):
    """Dispatch a JSON view and translate ApiError into the error envelope."""

    allowed = tuple(methods)

    def decorator(view):
        @csrf_exempt
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method not in allowed:
                response = error_response(
                    405,
                    "method_not_allowed",
                    f"Method {request.method} is not allowed for this resource.",
                )
                response["Allow"] = ", ".join(allowed)
                return response
            try:
                return view(request, *args, **kwargs)
            except ApiError as exc:
                return error_response(exc.status, exc.code, exc.message, exc.details)

        return wrapper

    return decorator


def read_json(request):
    content_type = (request.content_type or "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise ApiError(
            415,
            "unsupported_media_type",
            "Content-Type must be application/json.",
        )
    raw = request.body
    if not raw:
        raise ApiError(400, "invalid_json", "Request body must be a JSON object.")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ApiError(400, "invalid_json", "Request body must be valid JSON.")
    if not isinstance(data, dict):
        raise ApiError(400, "invalid_json", "JSON body must be an object.")
    return data
