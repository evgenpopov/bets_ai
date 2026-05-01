import json
import datetime
from django.utils import timezone

from django.contrib import messages
from django.db.models import Sum, Q, Count, FloatField
from django.db.models.functions import Cast
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect

from .forms import RegisterForm
from .models import ModelAI, Match, Prediction, BalanceHistory
from .tasks import import_matches_and_predictions, update_matches_and_predictions


def index(request):
    models_qs = ModelAI.objects.annotate(
        pending_bets=Sum(
            "predictions__bet_amount",
            filter=Q(predictions__result__isnull=True)
        ),
        total_predictions=Count(
            "predictions",
            filter=Q(predictions__result__isnull=False)
        ),
        positive_predictions=Count(
            "predictions",
            filter=Q(predictions__result__isnull=False) & ~Q(predictions__result__startswith='-')
        )
    )

    models_with_pending = []
    for m in models_qs:
        total = m.total_predictions or 0
        positive = m.positive_predictions or 0
        percent_positive = round((positive / total * 100), 2) if total > 0 else 0
        pending = m.pending_bets or 0

        display_balance = BalanceHistory.objects.filter(ai_model=m).last().balance

        models_with_pending.append({
            "id": m.id,
            "slug": m.slug,
            "name": m.name,
            "balance": m.balance,
            "pending_bets": pending,
            "roi": round((display_balance - 1000) / 1000 * 100, 2),
            "winrate": percent_positive,
            "display_balance": display_balance,
        })


    last_completed_date = Prediction.objects.filter(result__isnull=False).order_by("-match__date").values_list("match__date", flat=True).first()
    if last_completed_date:
        completed_bets = Prediction.objects.filter(
            result__isnull=False,
            match__date=last_completed_date
        ).select_related("match", "ai_model").order_by("-id")
    else:
        completed_bets = Prediction.objects.none()

    account_type = getattr(request.user, 'profile', None)
    account_type = account_type.account_type if account_type else 'lite'

    if account_type != 'lite':
        today = datetime.date.today()
        upcoming_qs = Prediction.objects.filter(
            result__isnull=True,
            match__date__gte=today
        ).select_related("match", "ai_model").order_by("match__date")
        next_day = upcoming_qs.values_list("match__date", flat=True).first()
        upcoming_bets = upcoming_qs.filter(match__date=next_day) if next_day else Prediction.objects.none()
    else:
        upcoming_bets = Prediction.objects.none()

    history = BalanceHistory.objects.filter(
        date__gte=datetime.datetime.now().replace(year=2026).replace(month=5).replace(day=1)
    ).select_related("ai_model").order_by("date")
    history_data = {}
    for h in history:
        history_data.setdefault(h.ai_model.name, []).append({
            "date": h.date.replace(hour=1, minute=0).strftime("%Y-%m-%d %H:%M"),
            "balance": float(h.balance)
        })
    history_json = json.dumps(history_data)
    last_update_obj = BalanceHistory.objects.order_by("-date").first()
    last_update = last_update_obj.date.replace(hour=1, minute=0, second=0) if last_update_obj else None

    return render(request, "core/index.html", {
        "request": request,
        "models": models_with_pending,
        "completed_bets": completed_bets,
        "upcoming_bets": upcoming_bets,
        "balance_history": history,
        "history_data": history_json,
        "last_update": last_update,
        "account_type": account_type,
    })


def model_detail(request, slug):
    model = get_object_or_404(ModelAI, slug=slug)

    predictions_qs = model.predictions.select_related('match').order_by('-id')
    paginator = Paginator(predictions_qs, 20)
    page_number = request.GET.get('page')
    predictions = paginator.get_page(page_number)

    pending_bets = model.predictions.filter(
        match__winner__isnull=True,
        match__date__gte=datetime.datetime.now().replace(year=2026).replace(month=5).replace(day=1)
    ).aggregate(total=Sum("bet_amount"))["total"] or 0

    stats = model.predictions.filter(
        result__isnull=False,
        match__date__gte=datetime.datetime.now().replace(year=2026).replace(month=5).replace(day=1)
    ).aggregate(
        total=Count("id"),
        positive=Count("id", filter=~Q(result__startswith='-'))
    )
    total = stats["total"] or 0
    positive = stats["positive"] or 0
    percent_positive = round((positive / total * 100), 2) if total > 0 else 0

    display_balance = BalanceHistory.objects.filter(ai_model=model).last().balance

    account_type = getattr(request.user, 'profile', None)
    account_type = account_type.account_type if account_type else 'lite'

    return render(request, 'core/model_detail.html', {
        'model': model,
        'roi': round((display_balance - 1000) / 1000 * 100, 2),
        'winrate': percent_positive,
        'predictions': predictions,
        'pending_bets': pending_bets,
        'display_balance': display_balance,
        'account_type': account_type,
    })


def event_detail(request, event_id):
    event = get_object_or_404(Match, id=event_id)

    info = {}
    comments = {}
    for prediction in Prediction.objects.filter(match=event):
        if prediction.comment:
            comments[prediction.ai_model.name] = prediction.comment

        info[prediction.ai_model.name] = {
            'bet_amount': prediction.bet_amount,
            'predicted_winner': prediction.predicted_winner,
            'odds': prediction.odds,
        }

    event_odds = event.odds
    # if 'No' in event_odds:
    #     event_odds['BTTS No'] = event_odds.pop('No')
    # if 'Yes' in event_odds:
    #     event_odds['BTTS Yes'] = event_odds.pop('Yes')

    account_type = getattr(request.user, 'profile', None)
    account_type = account_type.account_type if account_type else 'lite'

    return render(request, 'core/event_detail.html', {
        'match': event,
        'comments': comments,
        'info': info,
        'odds': event_odds,
        'account_type': account_type
    })


def import_matches(request):
    import_matches_and_predictions.apply_async()
    return redirect('index')


def update_matches(request):
    update_matches_and_predictions.apply_async()
    return redirect('index')


def register_view(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("login")
    else:
        form = RegisterForm()

    return render(request, "core/register.html", {"form": form})


@login_required
def profile_view(request):
    profile = getattr(request.user, 'profile', None)
    account_type = profile.account_type if profile else 'lite'

    return render(request, "core/profile.html", {
        "account_type": account_type
    })

@login_required
def profile_view(request):
    profile = getattr(request.user, 'profile', None)
    if not profile:
        messages.error(request, "Profile not found.")
        return redirect("index")

    if request.method == "POST" and "upgrade" in request.POST:
        if profile.account_type == "premium":
            messages.info(request, "You are already a Premium user!")
        else:
            # Здесь в будущем можно интегрировать платежную систему
            profile.account_type = "premium"
            profile.save()
            messages.success(request, "Your account has been upgraded to Premium!")

        return redirect("profile")

    return render(request, "core/profile.html", {"profile": profile})


@login_required
def subscription(request):
    profile = request.user.profile

    if request.method == 'POST':
        if profile.account_type == "premium":
            messages.info(request, "You are already a Premium user!")
        else:
            # Здесь в будущем можно интегрировать платежную систему
            profile.account_type = "premium"
            profile.save()
            messages.success(request, "Your account has been upgraded to Premium!")

    return render(request, 'core/subscription.html', {
        'profile': profile
    })

def terms(request):
    return render(request, 'core/terms.html')

def refund(request):
    return render(request, 'core/refund.html')

def contacts(request):
    return render(request, 'core/contacts.html')


def archive(request):
    ARCHIVE_CUTOFF = datetime.date(2026, 5, 1)
    ARCHIVE_CUTOFF_DT = timezone.make_aware(datetime.datetime(2026, 5, 1, 0, 0, 0))
    all_dates = (
        BalanceHistory.objects
        .filter(date__lt=ARCHIVE_CUTOFF_DT)
        .values_list("date", flat=True)
        .order_by("date")
    )
    available_months = sorted({d.strftime("%Y-%m") for d in all_dates}, reverse=True)


    # По умолчанию — весь архив
    period_start = None
    period_end = ARCHIVE_CUTOFF_DT

    history_qs = BalanceHistory.objects.filter(date__lt=period_end)
    if period_start:
        history_qs = history_qs.filter(date__gte=period_start)
    history_qs = history_qs.select_related("ai_model").order_by("date")

    history_data = {}
    for h in history_qs:
        history_data.setdefault(h.ai_model.name, []).append({
            "date": h.date.strftime("%Y-%m-%d %H:%M"),
            "balance": float(h.balance),
        })
    history_json = json.dumps(history_data)

    predictions_base = Prediction.objects.filter(
        result__isnull=False,
        match__date__lt=ARCHIVE_CUTOFF,
    )
    if period_start:
        predictions_base = predictions_base.filter(
            match__date__gte=period_start.date()
        )
    if period_end < ARCHIVE_CUTOFF_DT:
        predictions_base = predictions_base.filter(
            match__date__lt=period_end.date()
        )

    model_stats = []
    for model in ModelAI.objects.all():
        qs = predictions_base.filter(ai_model=model)
        stats = qs.aggregate(
            total=Count("id"),
            positive=Count("id", filter=~Q(result__startswith="-")),
            total_profit=Sum(Cast("result", output_field=FloatField())),
        )
        total = stats["total"] or 0
        positive = stats["positive"] or 0
        profit = float(stats["total_profit"] or 0)
        winrate = round(positive / total * 100, 1) if total > 0 else 0

        if period_start:
            start_balance_obj = (
                BalanceHistory.objects
                .filter(ai_model=model, date__lte=period_start)
                .order_by("-date")
                .first()
            )
        else:
            start_balance_obj = (
                BalanceHistory.objects
                .filter(ai_model=model)
                .order_by("date")
                .first()
            )
        start_balance = float(start_balance_obj.balance) if start_balance_obj else 1000.0

        # Конечный баланс в конце периода
        end_balance_obj = (
            BalanceHistory.objects
            .filter(ai_model=model, date__lt=period_end)
            .order_by("-date")
            .first()
        )
        end_balance = float(end_balance_obj.balance) if end_balance_obj else start_balance

        roi = round((end_balance - start_balance) / start_balance * 100, 2) if start_balance else 0
        profit = end_balance - start_balance

        model_stats.append({
            "name": model.name,
            "slug": model.slug,
            "total": total,
            "positive": positive,
            "winrate": winrate,
            "profit": round(profit, 2),
            "start_balance": round(start_balance, 2),
            "end_balance": round(end_balance, 2),
            "roi": roi,
        })

    # Сортируем по ROI убыванию
    model_stats.sort(key=lambda x: x["roi"], reverse=True)

    # ── 5. Таблица ставок с пагинацией ───────────────────────────────────────
    bets_qs = (
        Prediction.objects
        .filter(result__isnull=False, match__date__lt=ARCHIVE_CUTOFF)
        .select_related("match", "ai_model")
        .order_by("-match__date", "-id")
    )
    if period_start:
        bets_qs = bets_qs.filter(match__date__gte=period_start.date())
    if period_end < ARCHIVE_CUTOFF_DT:
        bets_qs = bets_qs.filter(match__date__lt=period_end.date())

    model_filter = request.GET.get("model", "")
    if model_filter:
        bets_qs = bets_qs.filter(ai_model__slug=model_filter)

    paginator = Paginator(bets_qs, 30)
    page_number = request.GET.get("page")
    bets_page = paginator.get_page(page_number)

    # ── 6. Итоговая сводка ────────────────────────────────────────────────────
    totals = predictions_base.aggregate(
        grand_total=Count("id"),
        grand_positive=Count("id", filter=~Q(result__startswith="-")),
        grand_profit=Sum(Cast("result", output_field=FloatField())),
    )

    all_models = ModelAI.objects.all()

    return render(request, "core/archive.html", {
        "available_months": available_months,
        "period_start": period_start,
        "period_end": period_end,
        "history_json": history_json,
        "model_stats": model_stats,
        "bets_page": bets_page,
        "model_filter": model_filter,
        "all_models": all_models,
        "grand_total": totals["grand_total"] or 0,
        "grand_positive": totals["grand_positive"] or 0,
        "grand_profit": round(float(totals["grand_profit"] or 0), 2),
        "archive_cutoff": ARCHIVE_CUTOFF,
    })