import uuid
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator


class Book(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="books",
        verbose_name="Пользователь",
    )
    title = models.CharField(max_length=500, verbose_name="Название")
    author = models.CharField(max_length=300, verbose_name="Автор")
    cover = models.ImageField(
        upload_to="covers/", null=True, blank=True, verbose_name="Обложка"
    )
    file = models.FileField(upload_to="books/", verbose_name="Файл книги")
    flibusta_id = models.CharField(
        max_length=100, null=True, blank=True, verbose_name="ID Флибусты"
    )
    reading_progress = models.IntegerField(default=0, verbose_name="Прогресс чтения")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата добавления")
    last_read = models.DateTimeField(
        null=True, blank=True, verbose_name="Последнее чтение"
    )

    # Жаңа өрістер - 1-кезең
    is_favorite = models.BooleanField(default=False, verbose_name="Таңдаулы")
    rating = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="Рейтинг (1-5)",
    )

    class Meta:
        verbose_name = "Книга"
        verbose_name_plural = "Книги"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} - {self.author}"


class SearchHistory(models.Model):
    """Іздеу тарихы моделі"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="search_history",
        verbose_name="Пользователь",
    )
    query = models.CharField(max_length=500, verbose_name="Сұраныс")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Уақыты")

    class Meta:
        verbose_name = "Іздеу тарихы"
        verbose_name_plural = "Іздеу тарихы"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username}: {self.query}"


class Bookmark(models.Model):
    """Бетбелгілер моделі"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="bookmarks",
        verbose_name="Пользователь",
    )
    book = models.ForeignKey(
        Book,
        on_delete=models.CASCADE,
        related_name="bookmarks",
        verbose_name="Книга",
    )
    title = models.CharField(max_length=200, verbose_name="Атауы")
    scroll_position = models.FloatField(verbose_name="Прокрутка позициясы (%)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Күні")

    class Meta:
        verbose_name = "Бетбелгі"
        verbose_name_plural = "Бетбелгілер"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.book.title} - {self.title}"


class DailyReadingStats(models.Model):
    """Күнделікті оқу статистикасы"""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="reading_stats",
        verbose_name="Пользователь",
    )
    date = models.DateField(auto_now_add=True, verbose_name="Күн")
    seconds_read = models.IntegerField(default=0, verbose_name="Оқылған секундтар")

    class Meta:
        verbose_name = "Оқу статистикасы"
        verbose_name_plural = "Оқу статистикасы"
        unique_together = ["user", "date"]  # Бір күнде бір қолданушыға бір жазба

    def __str__(self):
        return f"{self.user.username} - {self.date}: {self.seconds_read}s"
