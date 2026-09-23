from django.db import models


class Author(models.Model):
    name = models.CharField(max_length=200)
    bio = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class Book(models.Model):
    title = models.CharField(max_length=300)
    isbn = models.CharField(max_length=13, unique=True)
    published_year = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=8, decimal_places=2)
    in_stock = models.BooleanField(default=True)
    description = models.TextField(blank=True, default="")
    author = models.ForeignKey(
        Author,
        related_name="books",
        on_delete=models.PROTECT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["title"]),
            models.Index(fields=["published_year"]),
        ]

    def __str__(self):
        return self.title
