from django.urls import path

from books import views

urlpatterns = [
    path("books", views.book_collection, name="book-collection"),
    path("books/<str:book_id>", views.book_detail, name="book-detail"),
    path("authors", views.author_collection, name="author-collection"),
    path("authors/<str:author_id>", views.author_detail, name="author-detail"),
]
