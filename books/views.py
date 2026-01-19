import os
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from django.core.files import File
from django.db.models import Q
from django.contrib import messages
from django.utils import timezone
from .models import Book, SearchHistory, Bookmark, DailyReadingStats
from .services.flibusta_service import FlibustaService
from .services.fb2_parser import FB2Parser
from .services.reading_service import ReadingService
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.decorators import login_required
from .utils import is_htmx


@require_http_methods(["GET"])
def library_view(request):
    # Если пользователь не авторизован, показываем лендинг
    if not request.user.is_authenticated:
        return render(request, "books/landing.html")

    # Логика библиотеки для авторизованных
    books = Book.objects.filter(user=request.user)
    query = request.GET.get("q", "").strip()
    flibusta_results = []
    flibusta_error = None

    if query:
        books = books.filter(Q(title__icontains=query) | Q(author__icontains=query))

        # Іздеу тарихына сақтау (тек бірінші 10)
        if not SearchHistory.objects.filter(user=request.user, query=query).exists():
            SearchHistory.objects.create(user=request.user, query=query)
            # Ескі жазбаларды тазалау (10-нан артық болса)
            old_history = SearchHistory.objects.filter(user=request.user)[10:]
            for item in old_history:
                item.delete()

        try:
            service = FlibustaService()
            flibusta_results = service.search(query)
        except Exception as e:
            flibusta_error = str(e)

    # Іздеу тарихын алу
    search_history = SearchHistory.objects.filter(user=request.user)[:5]
    favorites_count = Book.objects.filter(user=request.user, is_favorite=True).count()

    context = {
        "books": books,
        "query": query,
        "flibusta_results": flibusta_results,
        "flibusta_error": flibusta_error,
        "is_htmx": is_htmx(request),
        "search_history": search_history,
        "favorites_count": favorites_count,
    }

    if is_htmx(request):
        if query:
            return render(request, "books/partials/search_results.html", context)
        return render(request, "books/partials/library_content.html", context)

    return render(request, "books/library.html", context)


@require_http_methods(["GET"])
def book_detail_view(request, book_id):
    # Проверяем, что книга принадлежит текущему пользователю
    book = get_object_or_404(Book, id=book_id, user=request.user)
    book.last_read = timezone.now()
    book.save(update_fields=["last_read"])

    try:
        text = ReadingService.get_book_text(book_id)
        context = {"book": book, "text": text, "is_htmx": is_htmx(request)}

        if is_htmx(request):
            return render(request, "books/partials/reader_content.html", context)

        return render(request, "books/reader.html", context)
    except Exception as e:
        if is_htmx(request):
            return HttpResponse(
                f'<div class="error text-red-400">{str(e)}</div>', status=400
            )
        return render(request, "books/error.html", {"error": str(e)})


@require_http_methods(["POST"])
def update_progress_view(request, book_id):
    try:
        progress = request.POST.get("progress", 0)
        ReadingService.update_progress(book_id, progress)
        return HttpResponse(status=204)
    except Exception as e:
        return HttpResponse(f"Error: {str(e)}", status=400)


@require_http_methods(["GET"])
def search_view(request):
    query = request.GET.get("q", "").strip()

    if not query:
        return render(request, "books/partials/flibusta_results.html", {"results": []})

    if not request.user.is_authenticated:
        return render(
            request,
            "books/partials/flibusta_results.html",
            {
                "results": [],
                "error": "Поиск на Флибусте доступен только для авторизованных пользователей",
            },
        )

    try:
        service = FlibustaService()
        results = service.search(query)
        return render(
            request, "books/partials/flibusta_results.html", {"results": results}
        )
    except Exception as e:
        return render(
            request,
            "books/partials/flibusta_results.html",
            {"results": [], "error": str(e)},
        )


@require_http_methods(["POST"])
def download_book_view(request):
    if not request.user.is_authenticated:
        return HttpResponse(
            '<div class="error">Скачивание с Флибусты доступно только для авторизованных пользователей</div>',
            status=403,
        )

    book_id = request.POST.get("book_id")
    title = request.POST.get("title", "Без названия")
    author = request.POST.get("author", "Неизвестный автор")

    if not book_id:
        return HttpResponse('<div class="error">Не указан ID книги</div>', status=400)

    try:
        service = FlibustaService()
        file_path = service.download_book(book_id)

        parser = FB2Parser(file_path)
        book_data = parser.parse()

        book = Book()
        book.user = request.user  # Привязываем книгу к текущему пользователю
        book.title = book_data.get("title", title)
        book.author = book_data.get("author", author)
        book.flibusta_id = book_id

        with open(file_path, "rb") as f:
            book.file.save(os.path.basename(file_path), File(f), save=False)

        if book_data.get("cover"):
            book.cover = book_data["cover"]

        book.save()

        if os.path.exists(file_path):
            os.remove(file_path)

        if is_htmx(request):
            messages.success(request, f'Книга "{book.title}" успешно скачана')

            books = Book.objects.filter(user=request.user)
            context = {
                "books": books,
                "query": "",
                "flibusta_results": [],
                "flibusta_error": None,
                "is_htmx": True,
            }
            return render(request, "books/partials/library_content.html", context)

        return HttpResponse("OK")

    except Exception as e:
        return HttpResponse(f'<div class="error">Ошибка: {str(e)}</div>', status=400)


@require_http_methods(["DELETE", "POST"])
def delete_book_view(request, book_id):
    try:
        # Только владелец может удалить книгу
        book = get_object_or_404(Book, id=book_id, user=request.user)

        if book.file:
            if os.path.exists(book.file.path):
                os.remove(book.file.path)

        if book.cover:
            if os.path.exists(book.cover.path):
                os.remove(book.cover.path)

        book.delete()

        if is_htmx(request):
            messages.success(request, "Книга удалена")
            return HttpResponse("")

        return HttpResponse("OK")
    except Exception as e:
        return HttpResponse(f'<div class="error">{str(e)}</div>', status=400)


@require_http_methods(["GET"])
def last_read_view(request):
    if not request.user.is_authenticated:
        return redirect("books:library")

    last_book = (
        Book.objects.filter(user=request.user, last_read__isnull=False)
        .order_by("-last_read")
        .first()
    )

    if not last_book:
        first_book = Book.objects.filter(user=request.user).first()
        if first_book:
            return redirect("books:book_detail", book_id=first_book.id)
        else:
            return redirect("books:library")

    return redirect("books:book_detail", book_id=last_book.id)


@require_http_methods(["GET"])
def sitemap_view(request):
    books = Book.objects.all()

    sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    sitemap_xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

    sitemap_xml += "  <url>\n"
    sitemap_xml += f"    <loc>{request.scheme}://{request.get_host()}/</loc>\n"
    sitemap_xml += "    <changefreq>daily</changefreq>\n"
    sitemap_xml += "    <priority>1.0</priority>\n"
    sitemap_xml += "  </url>\n"

    for book in books:
        sitemap_xml += "  <url>\n"
        sitemap_xml += (
            f"    <loc>{request.scheme}://{request.get_host()}/book/{book.id}/</loc>\n"
        )
        sitemap_xml += (
            f'    <lastmod>{book.created_at.strftime("%Y-%m-%d")}</lastmod>\n'
        )
        sitemap_xml += "    <changefreq>monthly</changefreq>\n"
        sitemap_xml += "    <priority>0.8</priority>\n"
        sitemap_xml += "  </url>\n"

    sitemap_xml += "</urlset>"

    return HttpResponse(sitemap_xml, content_type="application/xml")


@require_http_methods(["GET"])
def robots_view(request):
    robots_txt = f"""User-agent: *
Allow: /
Disallow: /admin/
Disallow: /book/*/delete/
Disallow: /download/
Disallow: /search/

Sitemap: {request.scheme}://{request.get_host()}/sitemap.xml
"""
    return HttpResponse(robots_txt, content_type="text/plain")


@require_http_methods(["GET"])
def offline_view(request):
    """Страница для offline режима PWA"""
    return render(request, "books/offline.html")


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect("books:library")

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect("books:library")
    else:
        form = AuthenticationForm()

    return render(request, "books/login.html", {"form": form})


@require_http_methods(["GET", "POST"])
def register_view(request):
    if request.user.is_authenticated:
        return redirect("books:library")

    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("books:library")
    else:
        form = UserCreationForm()

    return render(request, "books/register.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("books:library")


# ============================================
# 1-КЕЗЕҢ: Жаңа мүмкіндіктер
# ============================================


@require_http_methods(["POST"])
@login_required
def toggle_favorite_view(request, book_id):
    """Кітапты таңдаулыларға қосу/алу"""
    book = get_object_or_404(Book, id=book_id, user=request.user)
    book.is_favorite = not book.is_favorite
    book.save(update_fields=["is_favorite"])

    if is_htmx(request):
        return render(request, "books/partials/favorite_button.html", {"book": book})

    return HttpResponse("OK")


@require_http_methods(["POST"])
@login_required
def set_rating_view(request, book_id):
    """Кітапқа рейтинг қою"""
    book = get_object_or_404(Book, id=book_id, user=request.user)
    rating = request.POST.get("rating")

    if rating:
        rating = int(rating)
        if 1 <= rating <= 5:
            book.rating = rating
            book.save(update_fields=["rating"])

    if is_htmx(request):
        return render(request, "books/partials/rating_stars.html", {"book": book})

    return HttpResponse("OK")


@require_http_methods(["GET"])
@login_required
def favorites_view(request):
    """Таңдаулы кітаптар тізімі"""
    books = Book.objects.filter(user=request.user, is_favorite=True)

    context = {
        "books": books,
        "is_favorites_page": True,
    }

    if is_htmx(request):
        return render(request, "books/partials/library_content.html", context)

    return render(request, "books/library.html", context)


@require_http_methods(["GET"])
@login_required
def search_history_view(request):
    """Іздеу тарихын көрсету"""
    history = SearchHistory.objects.filter(user=request.user)[:10]

    if is_htmx(request):
        return render(
            request, "books/partials/search_history.html", {"history": history}
        )

    return render(request, "books/partials/search_history.html", {"history": history})


@require_http_methods(["POST"])
@login_required
def clear_search_history_view(request):
    """Іздеу тарихын тазалау"""
    SearchHistory.objects.filter(user=request.user).delete()

    if is_htmx(request):
        return HttpResponse("")

    return redirect("books:library")


# ============================================
# 2-КЕЗЕҢ: Бетбелгілер және Статистика
# ============================================


@require_http_methods(["POST"])
@login_required
def add_bookmark_view(request, book_id):
    """Бетбелгі қосу"""
    book = get_object_or_404(Book, id=book_id, user=request.user)
    title = request.POST.get("title", f"Бетбелгі {timezone.now().strftime('%H:%M')}")
    scroll_position = request.POST.get("scroll_position")

    if scroll_position:
        Bookmark.objects.create(
            user=request.user,
            book=book,
            title=title,
            scroll_position=float(scroll_position),
        )

    bookmarks = Bookmark.objects.filter(book=book)
    return render(
        request,
        "books/partials/bookmarks_list.html",
        {"bookmarks": bookmarks, "book": book},
    )


@require_http_methods(["DELETE", "POST"])
@login_required
def delete_bookmark_view(request, bookmark_id):
    """Бетбелгіні өшіру"""
    bookmark = get_object_or_404(Bookmark, id=bookmark_id, user=request.user)
    book = bookmark.book
    bookmark.delete()

    bookmarks = Bookmark.objects.filter(book=book)
    return render(
        request,
        "books/partials/bookmarks_list.html",
        {"bookmarks": bookmarks, "book": book},
    )


@require_http_methods(["POST"])
@login_required
def track_time_view(request):
    """Оқу уақытын тіркеу (әр 60 секунд сайын шақырылады)"""
    seconds = int(request.POST.get("seconds", 60))
    today = timezone.now().date()

    stats, created = DailyReadingStats.objects.get_or_create(
        user=request.user, date=today
    )
    stats.seconds_read += seconds
    stats.save()

    return HttpResponse("OK")


@login_required
def profile_view(request):
    """Профиль және статистика беті"""
    today = timezone.now().date()

    # Бүгінгі статистика
    today_stats, _ = DailyReadingStats.objects.get_or_create(
        user=request.user, date=today
    )

    # Жалпы статистика
    total_seconds = 0
    all_stats = DailyReadingStats.objects.filter(user=request.user)
    for stat in all_stats:
        total_seconds += stat.seconds_read

    context = {
        "today_minutes": today_stats.seconds_read // 60,
        "total_hours": total_seconds // 3600,
        "total_books": Book.objects.filter(user=request.user).count(),
        "read_books": Book.objects.filter(
            user=request.user, reading_progress=100
        ).count(),
    }

    return render(request, "books/profile.html", context)
