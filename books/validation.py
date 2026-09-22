from datetime import date
from decimal import Decimal, InvalidOperation

from books.exceptions import ApiError
from books.models import Author

BOOK_FIELDS = {
    "title",
    "isbn",
    "published_year",
    "price",
    "in_stock",
    "description",
    "author_id",
}
AUTHOR_FIELDS = {"name", "bio"}
BOOK_REQUIRED = ("title", "isbn", "published_year", "price", "author_id")
AUTHOR_REQUIRED = ("name",)
TEXT_LIMIT = 5000
MAX_PRICE = Decimal("999999.99")


def make_isbn13(serial):
    """Return a valid ISBN-13 whose body is derived from ``serial``."""

    body = f"{serial % 1_000_000_000:09d}"
    stem = "978" + body
    total = sum(int(char) if index % 2 == 0 else int(char) * 3 for index, char in enumerate(stem))
    check = (10 - (total % 10)) % 10
    return stem + str(check)


def validate_book(data, partial=False):
    errors = {}
    _reject_unknown(data, BOOK_FIELDS, errors)
    if not partial:
        _require_fields(data, BOOK_REQUIRED, errors)
    _reject_nulls(data, BOOK_FIELDS, errors)

    cleaned = {}
    if _should_parse(data, "title"):
        cleaned["title"] = _parse_required_string(data.get("title"), "title", 300, errors)
    if _should_parse(data, "isbn"):
        cleaned["isbn"] = _parse_isbn(data.get("isbn"), errors)
    if _should_parse(data, "published_year"):
        cleaned["published_year"] = _parse_year(data.get("published_year"), errors)
    if _should_parse(data, "price"):
        cleaned["price"] = _parse_price(data.get("price"), errors)
    if _should_parse(data, "author_id"):
        cleaned["author_id"] = _parse_author_id(data.get("author_id"), errors)
    if _should_parse(data, "in_stock"):
        cleaned["in_stock"] = _parse_bool(data.get("in_stock"), "in_stock", errors)
    elif not partial and "in_stock" not in data:
        cleaned["in_stock"] = True
    if _should_parse(data, "description"):
        cleaned["description"] = _parse_text(data.get("description"), "description", errors)
    elif not partial:
        cleaned["description"] = ""

    _raise_if_errors(errors)
    return {key: value for key, value in cleaned.items() if key not in errors}


def validate_author(data, partial=False):
    errors = {}
    _reject_unknown(data, AUTHOR_FIELDS, errors)
    if not partial:
        _require_fields(data, AUTHOR_REQUIRED, errors)
    _reject_nulls(data, AUTHOR_FIELDS, errors)

    cleaned = {}
    if _should_parse(data, "name"):
        cleaned["name"] = _parse_required_string(data.get("name"), "name", 200, errors)
    if _should_parse(data, "bio"):
        cleaned["bio"] = _parse_text(data.get("bio"), "bio", errors)
    elif not partial:
        cleaned["bio"] = ""

    _raise_if_errors(errors)
    return {key: value for key, value in cleaned.items() if key not in errors}


def parse_page_params(params):
    page = _parse_query_int(params.get("page"), "page", default=1, minimum=1, maximum=1_000_000)
    page_size = _parse_query_int(
        params.get("page_size"),
        "page_size",
        default=20,
        minimum=1,
        maximum=100,
    )
    return page, page_size


def parse_ordering(params, allowed, default="id"):
    raw = params.get("ordering")
    if raw in (None, ""):
        return default
    if raw not in allowed:
        raise ApiError(
            400,
            "validation_error",
            "Request validation failed.",
            {"ordering": [f"Must be one of: {', '.join(allowed)}."]},
        )
    return raw


def parse_search(params):
    search = params.get("search", "")
    if search is None:
        return ""
    if len(search) > 200:
        raise ApiError(
            400,
            "validation_error",
            "Request validation failed.",
            {"search": ["Must be at most 200 characters."]},
        )
    return search


def parse_optional_bool(params, field):
    if field not in params:
        return None
    raw = params.get(field, "")
    if raw not in {"true", "false"}:
        raise ApiError(
            400,
            "validation_error",
            "Request validation failed.",
            {field: ["Must be true or false."]},
        )
    return raw == "true"


def parse_optional_pk(params, field):
    if field not in params:
        return None
    return _parse_query_int(params.get(field), field, default=None, minimum=1, maximum=2**63 - 1)


def _should_parse(data, field):
    return field in data and data[field] is not None


def _require_fields(data, fields, errors):
    for field in fields:
        if field not in data:
            _add(errors, field, "This field is required.")


def _reject_nulls(data, allowed, errors):
    for field, value in data.items():
        if value is None and field in allowed:
            _add(errors, field, "Must not be null.")


def _reject_unknown(data, allowed, errors):
    for field in sorted(set(data) - allowed):
        _add(errors, field, "Unknown field.")


def _parse_required_string(value, field, max_length, errors):
    if field in errors:
        return None
    if not isinstance(value, str):
        _add(errors, field, "Must be a string.")
        return None
    cleaned = value.strip()
    if not cleaned:
        _add(errors, field, "This field is required.")
        return None
    if len(cleaned) > max_length:
        _add(errors, field, f"Must be at most {max_length} characters.")
        return None
    return cleaned


def _parse_text(value, field, errors):
    if not isinstance(value, str):
        _add(errors, field, "Must be a string.")
        return None
    if len(value) > TEXT_LIMIT:
        _add(errors, field, f"Must be at most {TEXT_LIMIT} characters.")
        return None
    return value


def _parse_isbn(value, errors):
    if "isbn" in errors:
        return None
    if not isinstance(value, str):
        _add(errors, "isbn", "Must be a string.")
        return None
    compact = value.replace("-", "").replace(" ", "").upper()
    if not (_isbn10_ok(compact) or _isbn13_ok(compact)):
        _add(errors, "isbn", "Must be a valid ISBN-10 or ISBN-13.")
        return None
    return compact


def _isbn10_ok(isbn):
    if len(isbn) != 10 or not isbn[:9].isdigit():
        return False
    if not (isbn[9].isdigit() or isbn[9] == "X"):
        return False
    total = 0
    for index, char in enumerate(isbn):
        number = 10 if char == "X" else int(char)
        total += number * (10 - index)
    return total % 11 == 0


def _isbn13_ok(isbn):
    if len(isbn) != 13 or not isbn.isdigit():
        return False
    total = sum(int(char) if index % 2 == 0 else int(char) * 3 for index, char in enumerate(isbn))
    return total % 10 == 0


def _parse_year(value, errors):
    if "published_year" in errors:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        _add(errors, "published_year", "Must be an integer.")
        return None
    upper = date.today().year + 1
    if value < 1450 or value > upper:
        _add(errors, "published_year", f"Must be between 1450 and {upper}.")
        return None
    return value


def _parse_price(value, errors):
    if "price" in errors:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        _add(errors, "price", "Must be a number or a numeric string.")
        return None
    text = value.strip() if isinstance(value, str) else str(value).strip()
    if any(char in text for char in "eE") or text == "":
        _add(errors, "price", "Must be a number or a numeric string.")
        return None
    try:
        amount = Decimal(text)
    except InvalidOperation:
        _add(errors, "price", "Must be a number or a numeric string.")
        return None
    if amount < 0:
        _add(errors, "price", "Must be zero or greater.")
        return None
    if amount > MAX_PRICE:
        _add(errors, "price", "Must be at most 999999.99.")
        return None
    exponent = amount.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -2:
        _add(errors, "price", "Must have at most 2 decimal places.")
        return None
    return amount.quantize(Decimal("0.01"))


def _parse_author_id(value, errors):
    if "author_id" in errors:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        _add(errors, "author_id", "Must be an integer.")
        return None
    if value < 1:
        _add(errors, "author_id", "Must be a positive integer.")
        return None
    if not Author.objects.filter(pk=value).exists():
        _add(errors, "author_id", "Author not found.")
        return None
    return value


def _parse_bool(value, field, errors):
    if not isinstance(value, bool):
        _add(errors, field, "Must be a boolean.")
        return None
    return value


def _parse_query_int(raw, field, default, minimum, maximum):
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ApiError(
            400,
            "validation_error",
            "Request validation failed.",
            {field: ["Must be an integer."]},
        ) from None
    if value < minimum or value > maximum:
        raise ApiError(
            400,
            "validation_error",
            "Request validation failed.",
            {field: [f"Must be between {minimum} and {maximum}."]},
        )
    return value


def _add(errors, field, message):
    errors.setdefault(field, []).append(message)


def _raise_if_errors(errors):
    if errors:
        raise ApiError(400, "validation_error", "Request validation failed.", errors)
