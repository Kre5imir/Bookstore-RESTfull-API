from datetime import timezone as dt_timezone

from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from books.exceptions import ApiError
from books.http import api_view, empty_response, json_response, read_json
from books.models import Author, Book
from books.validation import (
    parse_optional_bool,
    parse_optional_pk,
    parse_ordering,
    parse_page_params,
    parse_search,
    validate_author,
    validate_book,
)

BOOK_ORDERING = (
    "id",
    "-id",
    "title",
    "-title",
    "published_year",
    "-published_year",
    "price",
    "-price",
)
AUTHOR_ORDERING = ("id", "-id", "name", "-name")


def iso_z(value):
    if timezone.is_naive(value):
        value = timezone.make_aware(value, dt_timezone.utc)
    return value.astimezone(dt_timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def author_payload(author):
    return {
        "id": author.id,
        "name": author.name,
        "bio": author.bio,
        "created_at": iso_z(author.created_at),
        "updated_at": iso_z(author.updated_at),
    }


def book_payload(book):
    return {
        "id": book.id,
        "title": book.title,
        "isbn": book.isbn,
        "published_year": book.published_year,
        "price": f"{book.price:.2f}",
        "in_stock": book.in_stock,
        "description": book.description,
        "author": {
            "id": book.author_id,
            "name": book.author.name,
            "href": f"/authors/{book.author_id}",
        },
        "created_at": iso_z(book.created_at),
        "updated_at": iso_z(book.updated_at),
    }


def page_payload(request, queryset, page, page_size, serializer):
    total = queryset.count()
    offset = (page - 1) * page_size
    results = [serializer(item) for item in queryset[offset : offset + page_size]]

    def link(target):
        query = request.GET.copy()
        query["page"] = str(target)
        encoded = query.urlencode()
        return f"{request.path}?{encoded}" if encoded else request.path

    return {
        "count": total,
        "page": page,
        "page_size": page_size,
        "next": link(page + 1) if offset + page_size < total else None,
        "previous": link(page - 1) if page > 1 and total else None,
        "results": results,
    }


def lookup_model(model, raw_id, label):
    try:
        pk = int(raw_id)
    except (TypeError, ValueError):
        raise ApiError(404, "not_found", f"{label} not found.") from None
    if pk < 1:
        raise ApiError(404, "not_found", f"{label} not found.")
    try:
        if model is Book:
            return Book.objects.select_related("author").get(pk=pk)
        return Author.objects.get(pk=pk)
    except model.DoesNotExist:
        raise ApiError(404, "not_found", f"{label} not found.") from None


def save_book(book, cleaned):
    if "isbn" in cleaned:
        conflict = Book.objects.filter(isbn=cleaned["isbn"])
        if book.pk:
            conflict = conflict.exclude(pk=book.pk)
        if conflict.exists():
            raise ApiError(
                409,
                "conflict",
                "A book with this ISBN already exists.",
                {"isbn": ["A book with this ISBN already exists."]},
            )
    if "author_id" in cleaned:
        book.author_id = cleaned["author_id"]
    for field in ("title", "isbn", "published_year", "price", "in_stock", "description"):
        if field in cleaned:
            setattr(book, field, cleaned[field])
    try:
        with transaction.atomic():
            book.save()
    except IntegrityError:
        raise ApiError(
            409,
            "conflict",
            "A book with this ISBN already exists.",
            {"isbn": ["A book with this ISBN already exists."]},
        ) from None
    return Book.objects.select_related("author").get(pk=book.pk)


def apply_author(author, cleaned):
    for field in ("name", "bio"):
        if field in cleaned:
            setattr(author, field, cleaned[field])
    author.save()
    return author


@api_view(["GET", "POST"])
def book_collection(request):
    if request.method == "GET":
        return list_books(request)
    return create_book(request)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
def book_detail(request, book_id):
    book = lookup_model(Book, book_id, "Book")
    if request.method == "GET":
        return json_response(book_payload(book))
    if request.method == "DELETE":
        book.delete()
        return empty_response(204)
    partial = request.method == "PATCH"
    updated = save_book(book, validate_book(read_json(request), partial=partial))
    return json_response(book_payload(updated))


@api_view(["GET", "POST"])
def author_collection(request):
    if request.method == "GET":
        return list_authors(request)
    return create_author(request)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
def author_detail(request, author_id):
    author = lookup_model(Author, author_id, "Author")
    if request.method == "GET":
        return json_response(author_payload(author))
    if request.method == "DELETE":
        try:
            author.delete()
        except ProtectedError:
            raise ApiError(
                409,
                "conflict",
                "Author cannot be deleted while books reference them.",
            ) from None
        return empty_response(204)
    partial = request.method == "PATCH"
    apply_author(author, validate_author(read_json(request), partial=partial))
    author.refresh_from_db()
    return json_response(author_payload(author))


def list_books(request):
    page, page_size = parse_page_params(request.GET)
    ordering = parse_ordering(request.GET, BOOK_ORDERING)
    search = parse_search(request.GET)
    author_id = parse_optional_pk(request.GET, "author_id")
    in_stock = parse_optional_bool(request.GET, "in_stock")

    books = Book.objects.select_related("author").all()
    if search:
        books = books.filter(title__icontains=search)
    if author_id is not None:
        books = books.filter(author_id=author_id)
    if in_stock is not None:
        books = books.filter(in_stock=in_stock)
    books = books.order_by(ordering)
    return json_response(page_payload(request, books, page, page_size, book_payload))


def create_book(request):
    book = save_book(Book(), validate_book(read_json(request)))
    location = request.build_absolute_uri(f"/books/{book.id}")
    return json_response(book_payload(book), status=201, headers={"Location": location})


def list_authors(request):
    page, page_size = parse_page_params(request.GET)
    ordering = parse_ordering(request.GET, AUTHOR_ORDERING)
    search = parse_search(request.GET)
    authors = Author.objects.all()
    if search:
        authors = authors.filter(name__icontains=search)
    authors = authors.order_by(ordering)
    return json_response(page_payload(request, authors, page, page_size, author_payload))


def create_author(request):
    author = Author()
    apply_author(author, validate_author(read_json(request)))
    location = request.build_absolute_uri(f"/authors/{author.id}")
    return json_response(author_payload(author), status=201, headers={"Location": location})
