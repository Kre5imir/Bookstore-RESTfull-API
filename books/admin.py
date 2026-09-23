from django.contrib import admin

from books.models import Author, Book

admin.site.site_header = "Readify Bookstore"
admin.site.site_title = "Readify Bookstore"
admin.site.index_title = "Catalog administration"


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_at", "updated_at")
    search_fields = ("name",)


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "isbn", "author", "price", "in_stock", "published_year")
    list_filter = ("in_stock", "published_year")
    search_fields = ("title", "isbn", "author__name")
