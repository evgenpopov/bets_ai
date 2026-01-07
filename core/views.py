import json
import datetime

from django.db.models import Sum, Q, Count
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404, redirect

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

    today = datetime.date.today()
    upcoming_qs = Prediction.objects.filter(
        result__isnull=True,
        match__date__gte=today
    ).select_related("match", "ai_model").order_by("match__date")
    next_day = upcoming_qs.values_list("match__date", flat=True).first()
    upcoming_bets = upcoming_qs.filter(match__date=next_day) if next_day else Prediction.objects.none()

    history = BalanceHistory.objects.select_related("ai_model").order_by("date")
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
    })


def model_detail(request, slug):
    model = get_object_or_404(ModelAI, slug=slug)

    predictions_qs = model.predictions.select_related('match').order_by('-id')
    paginator = Paginator(predictions_qs, 20)
    page_number = request.GET.get('page')
    predictions = paginator.get_page(page_number)

    pending_bets = model.predictions.filter(match__winner__isnull=True).aggregate(total=Sum("bet_amount"))["total"] or 0

    stats = model.predictions.filter(result__isnull=False).aggregate(
        total=Count("id"),
        positive=Count("id", filter=~Q(result__startswith='-'))
    )
    total = stats["total"] or 0
    positive = stats["positive"] or 0
    percent_positive = round((positive / total * 100), 2) if total > 0 else 0

    display_balance = BalanceHistory.objects.filter(ai_model=model).last().balance

    return render(request, 'core/model_detail.html', {
        'model': model,
        'roi': round((display_balance - 1000) / 1000 * 100, 2),
        'winrate': percent_positive,
        'predictions': predictions,
        'pending_bets': pending_bets,
        'display_balance': display_balance,
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

    return render(request, 'core/event_detail.html', {
        'match': event,
        'comments': comments,
        'info': info,
        'odds': event.odds
    })


def import_matches(request):
    import_matches_and_predictions.apply_async()
    return redirect('index')


def update_matches(request):
    update_matches_and_predictions.apply_async()
    return redirect('index')
