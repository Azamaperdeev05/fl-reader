from django.urls import path
from . import views

app_name = "books"

urlpatterns = [
    path("", views.library_view, name="library"),
    path("last-read/", views.last_read_view, name="last_read"),
    path("book/<uuid:book_id>/", views.book_detail_view, name="book_detail"),
    path(
        "book/<uuid:book_id>/progress/",
        views.update_progress_view,
        name="update_progress",
    ),
    path("search/", views.search_view, name="search"),
    path("download/", views.download_book_view, name="download"),
    path("book/<uuid:book_id>/delete/", views.delete_book_view, name="delete_book"),
    path("offline/", views.offline_view, name="offline"),
    path("sitemap.xml", views.sitemap_view, name="sitemap"),
    path("robots.txt", views.robots_view, name="robots"),
    path("login/", views.login_view, name="login"),
    path("register/", views.register_view, name="register"),
    path("logout/", views.logout_view, name="logout"),
    # 1-кезең: Жаңа мүмкіндіктер
    path("favorites/", views.favorites_view, name="favorites"),
    path(
        "book/<uuid:book_id>/favorite/",
        views.toggle_favorite_view,
        name="toggle_favorite",
    ),
    path("book/<uuid:book_id>/rating/", views.set_rating_view, name="set_rating"),
    path("search-history/", views.search_history_view, name="search_history"),
    path(
        "clear-search-history/",
        views.clear_search_history_view,
        name="clear_search_history",
    ),
    # 2-кезең: Бетбелгілер және статистика
    path("book/<uuid:book_id>/bookmark/", views.add_bookmark_view, name="add_bookmark"),
    path(
        "bookmark/<uuid:bookmark_id>/delete/",
        views.delete_bookmark_view,
        name="delete_bookmark",
    ),
    path("track-time/", views.track_time_view, name="track_time"),
    path("profile/", views.profile_view, name="profile"),
]
