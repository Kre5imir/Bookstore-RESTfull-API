from decimal import Decimal

from django.core.management.base import BaseCommand

from books.models import Author, Book


CATALOG = (
    {
        "author": {
            "name": "Ursula K. Le Guin",
            "bio": "American author of speculative fiction.",
        },
        "books": (
            {
                "title": "The Left Hand of Darkness",
                "isbn": "9780441478125",
                "published_year": 1969,
                "price": Decimal("14.99"),
                "description": "A novel set on the planet Gethen.",
            },
        ),
    },
    {
        "author": {
            "name": "Jane Austen",
            "bio": "English novelist known for social comedy.",
        },
        "books": (
            {
                "title": "Pride and Prejudice",
                "isbn": "9780141439518",
                "published_year": 1813,
                "price": Decimal("9.99"),
                "description": "A novel of manners set in rural England.",
            },
        ),
    },
    {
        "author": {
            "name": "Harper Lee",
            "bio": "American novelist.",
        },
        "books": (
            {
                "title": "To Kill a Mockingbird",
                "isbn": "9780061120084",
                "published_year": 1960,
                "price": Decimal("12.50"),
                "description": "A novel set in the American South.",
            },
        ),
    },
)


class Command(BaseCommand):
    help = "Insert a small sample catalog when the database has no authors yet."

    def handle(self, *args, **options):
        if Author.objects.exists():
            self.stdout.write("Authors already exist; leaving the catalog unchanged.")
            return
        for group in CATALOG:
            author = Author.objects.create(**group["author"])
            for book in group["books"]:
                Book.objects.create(author=author, in_stock=True, **book)
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {Author.objects.count()} authors and {Book.objects.count()} books."
            )
        )
