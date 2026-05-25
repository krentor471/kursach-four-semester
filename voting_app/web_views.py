from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Avg, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import Category, Nomination
from .services import cast_vote


def is_moderator(user) -> bool:
    """Проверяет права модератора для веб-форм."""
    return bool(
        user.is_authenticated
        and (user.is_staff or user.groups.filter(name="moderator").exists())
    )


def parse_form_datetime(value: str, fallback):
    """Разбирает datetime-local из HTML-формы."""
    if not value:
        return fallback
    parsed = parse_datetime(value)
    if parsed is None:
        return fallback
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def datetime_local_value(value) -> str:
    """Форматирует дату для input type=datetime-local."""
    return timezone.localtime(value).strftime("%Y-%m-%dT%H:%M")


def category_list(request):
    """Показывает список категорий с агрегированной статистикой."""
    categories = (
        Category.objects.prefetch_related("nominations", "nominations__votes")
        .annotate(
            nominations_count=Count("nominations", distinct=True),
            total_votes=Count("nominations__votes", distinct=True),
        )
        .order_by("-priority", "-created_at")
    )
    paginator = Paginator(categories, 5)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "category_list.html", {"categories": page_obj, "page_obj": page_obj})


def category_detail(request, pk: int):
    """Показывает категорию и ее номинации."""
    category = get_object_or_404(Category, pk=pk)
    nominations = (
        category.nominations.select_related("category")
        .prefetch_related("votes")
        .annotate(votes_count=Count("votes", distinct=True), average_rating=Avg("votes__rating"))
    )
    return render(
        request,
        "category_detail.html",
        {"category": category, "nominations": nominations},
    )


@user_passes_test(is_moderator)
def category_create(request):
    """Создает категорию через веб-форму."""
    if request.method == "POST":
        category = Category(
            name=request.POST.get("name", ""),
            description=request.POST.get("description", ""),
            is_active=request.POST.get("is_active") == "on",
            is_featured=request.POST.get("is_featured") == "on",
            priority=int(request.POST.get("priority") or 0),
            color=request.POST.get("color") or "#0078d4",
        )
        try:
            category.save()
        except ValidationError as error:
            messages.error(request, "; ".join(error.messages))
        else:
            messages.success(request, "Категория успешно создана.")
            return redirect("voting_app:category_list")
    return render(request, "category_form.html", {"title": "Создать категорию"})


@user_passes_test(is_moderator)
def category_edit(request, pk: int):
    """Редактирует категорию через веб-форму."""
    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        category.name = request.POST.get("name", category.name)
        category.description = request.POST.get("description", category.description)
        category.is_active = request.POST.get("is_active") == "on"
        category.is_featured = request.POST.get("is_featured") == "on"
        category.priority = int(request.POST.get("priority") or 0)
        category.color = request.POST.get("color") or "#0078d4"
        try:
            category.save()
        except ValidationError as error:
            messages.error(request, "; ".join(error.messages))
        else:
            messages.success(request, "Категория успешно обновлена.")
            return redirect("voting_app:category_list")
    return render(
        request,
        "category_form.html",
        {"category": category, "title": "Редактировать категорию"},
    )


@user_passes_test(is_moderator)
def category_delete(request, pk: int):
    """Удаляет категорию, если в ней нет номинаций."""
    category = get_object_or_404(Category, pk=pk)
    if request.method == "POST":
        if category.nominations.exists():
            messages.error(request, "Нельзя удалить категорию с номинациями.")
        else:
            category.delete()
            messages.success(request, "Категория удалена.")
        return redirect("voting_app:category_list")
    return render(request, "category_confirm_delete.html", {"category": category})


@login_required
def nomination_vote(request, pk: int):
    """Принимает голос пользователя из веб-формы."""
    nomination = get_object_or_404(
        Nomination.objects.select_related("category"),
        pk=pk,
    )
    if request.method == "POST":
        try:
            vote, created = cast_vote(
                nomination=nomination,
                user=request.user,
                rating=int(request.POST.get("rating", 0)),
                comment=request.POST.get("comment", ""),
            )
        except (ValueError, ValidationError) as error:
            messages.error(request, f"Голос не принят: {error}")
        else:
            action = "принят" if created else "обновлен"
            messages.success(request, f"Ваш голос за \"{vote.nomination.title}\" {action}.")
    return redirect("voting_app:category_detail", pk=nomination.category.pk)


@user_passes_test(is_moderator)
def nomination_create(request, category_id: int):
    """Создает номинацию в категории."""
    category = get_object_or_404(Category, pk=category_id)
    if request.method == "POST":
        default_start = timezone.now()
        default_end = timezone.now() + timedelta(days=7)
        nomination = Nomination(
            title=request.POST.get("title", ""),
            description=request.POST.get("description", ""),
            category=category,
            voting_start=parse_form_datetime(request.POST.get("voting_start", ""), default_start),
            voting_end=parse_form_datetime(request.POST.get("voting_end", ""), default_end),
            is_active=request.POST.get("is_active") == "on",
        )
        try:
            nomination.save()
        except ValidationError as error:
            messages.error(request, "; ".join(error.messages))
        else:
            messages.success(request, f"Номинация \"{nomination.title}\" создана.")
            return redirect("voting_app:category_detail", pk=category.pk)
    return render(
        request,
        "nomination_form.html",
        {
            "category": category,
            "title": "Добавить номинацию",
            "voting_start_value": datetime_local_value(timezone.now()),
            "voting_end_value": datetime_local_value(timezone.now() + timedelta(days=7)),
        },
    )


@user_passes_test(is_moderator)
def nomination_edit(request, pk: int):
    """Редактирует номинацию и сроки голосования."""
    nomination = get_object_or_404(Nomination.objects.select_related("category"), pk=pk)
    if request.method == "POST":
        nomination.title = request.POST.get("title", nomination.title)
        nomination.description = request.POST.get("description", nomination.description)
        nomination.voting_start = parse_form_datetime(
            request.POST.get("voting_start", ""),
            nomination.voting_start,
        )
        nomination.voting_end = parse_form_datetime(
            request.POST.get("voting_end", ""),
            nomination.voting_end,
        )
        nomination.is_active = request.POST.get("is_active") == "on"
        try:
            nomination.save()
        except ValidationError as error:
            messages.error(request, "; ".join(error.messages))
        else:
            messages.success(request, f"Номинация \"{nomination.title}\" обновлена.")
            return redirect("voting_app:category_detail", pk=nomination.category.pk)
    return render(
        request,
        "nomination_form.html",
        {
            "category": nomination.category,
            "nomination": nomination,
            "title": "Редактировать номинацию",
            "voting_start_value": datetime_local_value(nomination.voting_start),
            "voting_end_value": datetime_local_value(nomination.voting_end),
        },
    )


@user_passes_test(is_moderator)
def nomination_delete(request, pk: int):
    """Удаляет номинацию, если за нее еще не голосовали."""
    nomination = get_object_or_404(Nomination, pk=pk)
    category_pk = nomination.category.pk
    if request.method == "POST":
        if nomination.votes.exists():
            messages.error(request, "Нельзя удалить номинацию с голосами.")
        else:
            nomination.delete()
            messages.success(request, f"Номинация \"{nomination.title}\" удалена.")
        return redirect("voting_app:category_detail", pk=category_pk)
    return render(request, "nomination_confirm_delete.html", {"nomination": nomination})
