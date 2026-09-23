import json

from django.core.management import call_command
from django.test import TestCase

from books.management.commands.seed import CATALOG
from books.models import Author, Book
from books.validation import _isbn13_ok, make_isbn13


class ApiTestCase(TestCase):
    def setUp(self):
        self._serial = 1000

    def request_json(self, method, path, payload=None, request_id=None):
        extra = {}
        if request_id is not None:
            extra["HTTP_X_REQUEST_ID"] = request_id
        if payload is None:
            return getattr(self.client, method)(path, **extra)
        return getattr(self.client, method)(
            path,
            data=json.dumps(payload),
            content_type="application/json",
            **extra,
        )

    def create_author(self, name="Ursula K. Le Guin"):
        response = self.request_json(
            "post",
            "/authors",
            {"name": name, "bio": "Speculative fiction."},
        )
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def book_payload(self, author_id, **overrides):
        self._serial += 1
        payload = {
            "title": "The Left Hand of Darkness",
            "isbn": make_isbn13(self._serial),
            "published_year": 1969,
            "price": "14.99",
            "in_stock": True,
            "description": "A novel set on Gethen.",
            "author_id": author_id,
        }
        payload.update(overrides)
        return payload


class BookApiTests(ApiTestCase):
    def test_create_retrieve_update_delete_flow(self):
        author = self.create_author()
        created = self.request_json("post", "/books", self.book_payload(author["id"]))
        self.assertEqual(created.status_code, 201, created.content)
        body = created.json()
        self.assertTrue(created["Location"].endswith(f"/books/{body['id']}"))
        self.assertEqual(body["title"], "The Left Hand of Darkness")
        self.assertEqual(body["price"], "14.99")
        self.assertEqual(body["author"]["id"], author["id"])
        self.assertEqual(body["author"]["href"], f"/authors/{author['id']}")
        book_id = body["id"]

        retrieved = self.client.get(f"/books/{book_id}")
        self.assertEqual(retrieved.status_code, 200)
        self.assertEqual(retrieved.json()["isbn"], body["isbn"])

        listed = self.client.get("/books")
        self.assertEqual(listed.status_code, 200)
        listed_body = listed.json()
        self.assertEqual(listed_body["count"], 1)
        self.assertEqual(listed_body["results"][0]["id"], book_id)

        replacement = self.book_payload(
            author["id"],
            title="The Dispossessed",
            price=18,
            description="An ambiguous utopia.",
        )
        updated = self.request_json("put", f"/books/{book_id}", replacement)
        self.assertEqual(updated.status_code, 200, updated.content)
        self.assertEqual(updated.json()["title"], "The Dispossessed")
        self.assertEqual(updated.json()["price"], "18.00")
        self.assertEqual(updated.json()["isbn"], replacement["isbn"])

        patched = self.request_json("patch", f"/books/{book_id}", {"in_stock": False})
        self.assertEqual(patched.status_code, 200, patched.content)
        self.assertIs(patched.json()["in_stock"], False)
        self.assertEqual(patched.json()["title"], "The Dispossessed")

        deleted = self.client.delete(f"/books/{book_id}")
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(deleted.content, b"")
        missing = self.client.get(f"/books/{book_id}")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()["error"]["code"], "not_found")

    def test_put_replaces_omitted_optional_fields(self):
        author = self.create_author()
        created = self.request_json(
            "post",
            "/books",
            self.book_payload(author["id"], in_stock=False, description="Original."),
        )
        book_id = created.json()["id"]
        payload = self.book_payload(author["id"], title="Replacement")
        payload.pop("description")
        payload.pop("in_stock")
        updated = self.request_json("put", f"/books/{book_id}", payload)
        self.assertEqual(updated.status_code, 200, updated.content)
        self.assertEqual(updated.json()["description"], "")
        self.assertIs(updated.json()["in_stock"], True)
        self.assertEqual(updated.json()["title"], "Replacement")

    def test_missing_required_fields(self):
        response = self.request_json("post", "/books", {})
        self.assertEqual(response.status_code, 400)
        error = response.json()["error"]
        self.assertEqual(error["code"], "validation_error")
        for field in ("title", "isbn", "published_year", "price", "author_id"):
            self.assertIn("This field is required.", error["details"][field])

    def test_invalid_isbn_and_unknown_author(self):
        author = self.create_author()
        invalid = self.request_json(
            "post",
            "/books",
            self.book_payload(author["id"], isbn="9780441478126"),
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertIn("isbn", invalid.json()["error"]["details"])

        missing_author = self.request_json(
            "post",
            "/books",
            self.book_payload(9999),
        )
        self.assertEqual(missing_author.status_code, 400)
        self.assertIn("author_id", missing_author.json()["error"]["details"])

    def test_hyphenated_isbn_is_normalized(self):
        author = self.create_author()
        response = self.request_json(
            "post",
            "/books",
            self.book_payload(author["id"], isbn="978-0-441-47812-5"),
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["isbn"], "9780441478125")

    def test_duplicate_isbn_conflicts(self):
        author = self.create_author()
        isbn = make_isbn13(4242)
        first = self.request_json("post", "/books", self.book_payload(author["id"], isbn=isbn))
        self.assertEqual(first.status_code, 201, first.content)
        second = self.request_json(
            "post",
            "/books",
            self.book_payload(author["id"], title="Another title", isbn=isbn),
        )
        self.assertEqual(second.status_code, 409)
        self.assertEqual(second.json()["error"]["code"], "conflict")

    def test_list_filters_and_pagination(self):
        leguin = self.create_author("Ursula K. Le Guin")
        austen = self.create_author("Jane Austen")
        self.request_json(
            "post",
            "/books",
            self.book_payload(leguin["id"], title="The Dispossessed", in_stock=True),
        )
        self.request_json(
            "post",
            "/books",
            self.book_payload(austen["id"], title="Pride and Prejudice", in_stock=False),
        )
        filtered = self.client.get(f"/books?author_id={leguin['id']}&search=dispossessed&in_stock=true")
        self.assertEqual(filtered.status_code, 200, filtered.content)
        self.assertEqual(filtered.json()["count"], 1)
        self.assertEqual(filtered.json()["results"][0]["title"], "The Dispossessed")

        page = self.client.get("/books?page_size=1&ordering=title")
        self.assertEqual(page.status_code, 200, page.content)
        body = page.json()
        self.assertEqual(body["page_size"], 1)
        self.assertEqual(body["count"], 2)
        self.assertIsNotNone(body["next"])
        self.assertIsNone(body["previous"])
        self.assertEqual(len(body["results"]), 1)

        invalid = self.client.get("/books?page=0")
        self.assertEqual(invalid.status_code, 400)

    def test_unknown_book_id_and_method(self):
        missing = self.client.get("/books/not-an-id")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()["error"]["code"], "not_found")

        method = self.client.delete("/books")
        self.assertEqual(method.status_code, 405)
        self.assertIn("GET", method["Allow"])
        self.assertIn("POST", method["Allow"])

    def test_media_type_and_malformed_json(self):
        plain = self.client.post("/books", data="title=x", content_type="text/plain")
        self.assertEqual(plain.status_code, 415)
        self.assertEqual(plain.json()["error"]["code"], "unsupported_media_type")

        broken = self.client.post("/books", data="{nope", content_type="application/json")
        self.assertEqual(broken.status_code, 400)
        self.assertEqual(broken.json()["error"]["code"], "invalid_json")

        array = self.client.post("/books", data="[]", content_type="application/json")
        self.assertEqual(array.status_code, 400)
        self.assertEqual(array.json()["error"]["code"], "invalid_json")


class AuthorApiTests(ApiTestCase):
    def test_list_and_detail(self):
        created = self.create_author("Octavia Butler")
        listing = self.client.get("/authors?search=octavia")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["count"], 1)
        self.assertEqual(listing.json()["results"][0]["name"], "Octavia Butler")

        detail = self.client.get(f"/authors/{created['id']}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["bio"], "Speculative fiction.")

    def test_delete_author_with_books_conflicts(self):
        author = self.create_author()
        self.request_json("post", "/books", self.book_payload(author["id"]))
        blocked = self.client.delete(f"/authors/{author['id']}")
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.json()["error"]["code"], "conflict")
        self.assertTrue(Author.objects.filter(pk=author["id"]).exists())

        Book.objects.filter(author_id=author["id"]).delete()
        removed = self.client.delete(f"/authors/{author['id']}")
        self.assertEqual(removed.status_code, 204)
        self.assertEqual(self.client.get(f"/authors/{author['id']}").status_code, 404)

    def test_patch_author_name(self):
        author = self.create_author()
        response = self.request_json("patch", f"/authors/{author['id']}", {"name": "Ursula Le Guin"})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["name"], "Ursula Le Guin")
        self.assertEqual(response.json()["bio"], "Speculative fiction.")


class PlatformTests(ApiTestCase):
    def test_root_health_and_metrics(self):
        root = self.client.get("/")
        self.assertEqual(root.status_code, 200)
        self.assertEqual(root.json()["resources"]["books"], "/books")
        self.assertEqual(root.json()["resources"]["authors"], "/authors")

        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")
        self.assertEqual(health.json()["checks"]["database"], "ok")
        self.assertIn("uptime_seconds", health.json())

        metrics = self.client.get("/metrics")
        self.assertEqual(metrics.status_code, 200)
        body = metrics.content.decode()
        self.assertIn("bookstore_http_requests_total", body)
        self.assertIn('route="/health"', body)
        self.assertIn("bookstore_uptime_seconds", body)

    def test_request_id_and_access_log(self):
        with self.assertLogs("bookstore.access", level="INFO") as captured:
            response = self.client.get("/health", HTTP_X_REQUEST_ID="abc-123")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["X-Request-ID"], "abc-123")
        self.assertTrue(any("request_id=abc-123" in line for line in captured.output))
        self.assertTrue(any("path=/health" in line for line in captured.output))

        replaced = self.client.get("/health", HTTP_X_REQUEST_ID="bad id")
        self.assertEqual(replaced.status_code, 200)
        self.assertNotEqual(replaced["X-Request-ID"], "bad id")
        self.assertTrue(replaced["X-Request-ID"])

    def test_unknown_path_is_json(self):
        response = self.client.get("/does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "not_found")

    def test_openapi_documents_required_endpoints(self):
        response = self.client.get("/openapi.yaml")
        self.assertEqual(response.status_code, 200)
        spec = response.content.decode()
        self.assertIn("openapi: 3.0.3", spec)
        for snippet in (
            "/books:",
            "/books/{id}:",
            "/authors:",
            "operationId: listBooks",
            "operationId: createBook",
            "operationId: retrieveBook",
            "operationId: replaceBook",
            "operationId: deleteBook",
            "operationId: listAuthors",
            "'201'",
            "'204'",
            "'400'",
            "'404'",
            "'409'",
        ):
            self.assertIn(snippet, spec)

    def test_seed_command_loads_valid_catalog(self):
        for group in CATALOG:
            for book in group["books"]:
                self.assertTrue(_isbn13_ok(book["isbn"]))
        call_command("seed")
        self.assertEqual(Author.objects.count(), 3)
        self.assertEqual(Book.objects.count(), 3)
        call_command("seed")
        self.assertEqual(Author.objects.count(), 3)
