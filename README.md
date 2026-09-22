# Readify Bookstore API

REST API for the Readify catalog. Books and authors are separate resources, every endpoint is documented in OpenAPI, and GitHub Actions installs dependencies, runs Django and Postman tests, and deploys a staging copy after a merge to `main`.

## API design

URIs name resources. They do not encode actions, and they do not use a trailing slash.

| Method | URI | Result |
| --- | --- | --- |
| `GET` | `/books` | List books |
| `POST` | `/books` | Add a book |
| `GET` | `/books/{id}` | Retrieve a book |
| `PUT` | `/books/{id}` | Replace book details |
| `PATCH` | `/books/{id}` | Update the fields you send |
| `DELETE` | `/books/{id}` | Delete a book |
| `GET` | `/authors` | List authors |
| `POST` | `/authors` | Add an author |
| `GET` | `/authors/{id}` | Retrieve an author |
| `PUT` | `/authors/{id}` | Replace an author |
| `PATCH` | `/authors/{id}` | Update the fields you send |
| `DELETE` | `/authors/{id}` | Delete an author |

A book stores `author_id` and the response includes a short author object with `href` set to that author's URI, such as `/authors/1`. Clients that only need the catalog can read the embedded name. Clients that need the biography follow `href`.

`POST` returns `201 Created` and a `Location` header. `DELETE` returns `204 No Content` and an empty body. `PUT` is a full replacement: `title`, `isbn`, `published_year`, `price`, and `author_id` are required, and omitted `description` and `in_stock` go back to `""` and `true`. `PATCH` changes only the supplied fields.

Status codes stay consistent:

| Code | When |
| --- | --- |
| `400` | Validation failed, or the body is not a JSON object |
| `404` | The book, author, or path does not exist |
| `405` | The verb is not allowed for that URI (`Allow` lists the verbs that are) |
| `409` | The ISBN already exists, or the author still has books |
| `415` | A write request was not `application/json` |
| `503` | `/health` cannot reach the database |

Errors use one envelope:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed.",
    "details": {
      "title": ["This field is required."]
    }
  }
}
```

List responses are pages:

```json
{
  "count": 1,
  "page": 1,
  "page_size": 20,
  "next": null,
  "previous": null,
  "results": []
}
```

`GET /books` accepts `search`, `author_id`, `in_stock` (`true` or `false`), `ordering`, `page`, and `page_size` (1–100). `GET /authors` accepts `search`, `ordering`, `page`, and `page_size`. ISBN values may include hyphens; they are stored without hyphens after the ISBN-10 or ISBN-13 checksum passes. `price` may be sent as a string or a number and is always returned as a two-decimal string.

`GET /` is the service index. `GET /openapi.yaml` serves the specification in `openapi/openapi.yaml`.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed
python manage.py runserver
```

Optional environment variables are listed in `.env.example`.

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/books
```

Create an author, then a book:

```bash
curl -s -X POST http://127.0.0.1:8000/authors \
  -H 'Content-Type: application/json' \
  -d '{"name":"Ursula K. Le Guin","bio":"Speculative fiction."}'

curl -s -X POST http://127.0.0.1:8000/books \
  -H 'Content-Type: application/json' \
  -d '{"title":"The Dispossessed","isbn":"9780061054884","published_year":1974,"price":"15.00","author_id":1}'
```

Import `postman/bookstore.postman_collection.json` and `postman/bookstore.postman_environment.json` into Postman, or open `openapi/openapi.yaml` in an OpenAPI viewer.

The Django admin is at `/admin/` after you create a superuser with `python manage.py createsuperuser`.

## Tests

Django tests cover the book lifecycle, validation, conflicts, filtering, health, metrics, and the OpenAPI document:

```bash
python manage.py test
```

The Postman collection covers the same lifecycle from an HTTP client: create an author, create a book, retrieve it, replace it, patch the price, list it, delete it, confirm `404`, reject `{}` as a validation error, and list authors. Newman runs that collection against a live server:

```bash
bash scripts/run_api_tests.sh
```

The script migrates, starts `runserver` on port 8000, waits for `/health`, and runs Newman. Node.js is required for `npx newman`.

## CI/CD

`.github/workflows/ci-cd.yml` runs on pull requests and on pushes to `main`.

1. **Install dependencies** installs `requirements.txt` and imports Django.
2. **Run tests** installs dependencies, migrates, runs `python manage.py test`, then runs the Postman collection.
3. **Deploy to staging** runs only after those tests pass on a push to `main`. `scripts/deploy_staging.sh` writes `.staging/deploy-manifest.json`, migrates a staging SQLite database, runs Django's deployment check, boots the API with `DJANGO_DEBUG=false`, and requires `GET /health` to return success. Local staging is plain HTTP, so the deployment check still warns about HTTPS cookie and redirect settings. The staging process is stopped when the job finishes; the manifest and database path are the deploy record on that runner.

Set `DJANGO_SECRET_KEY` and `DJANGO_ALLOWED_HOSTS` in a real environment before pointing traffic at the process. `BOOKSTORE_DB_PATH` selects the SQLite file.

## Logging and monitoring

Each request gets an `X-Request-ID`. Send your own id (letters, digits, `_`, `-`, up to 64 characters) or the API generates one and returns it. Completed requests are written to stdout as one JSON object per line, including method, path, route, status, duration, and request id. Process start and shutdown are logged on the `bookstore.lifecycle` logger.

`GET /health` reports process uptime and a `SELECT 1` database check. Use it for liveness and readiness. `GET /metrics` exposes Prometheus counters for request totals and duration, labeled by method, route pattern, and status, plus `bookstore_uptime_seconds`. Point a scraper or uptime check at those two paths. Routes are the URI templates (`/books/{id}`), not raw ids, so the metric series stay bounded.
