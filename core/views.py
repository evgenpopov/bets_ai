import json
import datetime

from django.db.models import Sum, OuterRef, Subquery
from django.shortcuts import render, get_object_or_404, redirect

from .models import ModelAI, Match, Prediction, BalanceHistory
from .tasks import import_matches_and_predictions, update_matches_and_predictions


def index(request):
    models = ModelAI.objects.all()
    matches = Match.objects.all()

    completed = Prediction.objects.filter(result__isnull=False)
    if completed.exists():
        last_completed_dt = completed.order_by('-match__date').first().match.date
        last_completed_date = last_completed_dt.date() if hasattr(last_completed_dt, 'date') else last_completed_dt
        completed_bets = [
            p for p in completed.order_by('-id')
            if (p.match.date.date() if hasattr(p.match.date, "date") else p.match.date) == last_completed_date
        ]
    else:
        completed_bets = []

    upcoming = Prediction.objects.filter(result__isnull=True, match__date__gt=datetime.datetime.now().date())
    if upcoming.exists():
        next_day = upcoming.order_by('match__date').first().match.date
        upcoming_bets = upcoming.filter(match__date=next_day).order_by('match__date')
    else:
        upcoming_bets = Prediction.objects.none()

    balance_history = BalanceHistory.objects.select_related("ai_model").order_by("-date")
    history = BalanceHistory.objects.order_by("date")
    history_data = {}

    for h in history:
        model_name = h.ai_model.name
        history_data.setdefault(model_name, []).append({
            "date": h.date.strftime("%Y-%m-%d %H:%M"),
            "balance": float(h.balance)
        })
    history_json = json.dumps(history_data)

    models_with_pending = []
    for m in models:
        pending_bets = Prediction.objects.filter(
            ai_model=m,
            result__isnull=True
        ).aggregate(total=Sum("bet_amount"))["total"] or 0

        models_with_pending.append({
            "id": m.id,
            "slug": m.slug,
            "name": m.name,
            "balance": m.balance,
            "pending_bets": pending_bets,
            "display_balance": m.balance + pending_bets
        })

    return render(request, "core/index.html", {
        "request": request,
        "models": models_with_pending,
        "matches": matches,
        "completed_bets": completed_bets,
        "upcoming_bets": upcoming_bets,
        "balance_history": balance_history,
        "history_data": history_json,
    })


def model_detail(request, slug):
    model = get_object_or_404(ModelAI, slug=slug)
    predictions = model.predictions.select_related('match').order_by('-id')

    pending_bets = model.predictions.filter(
        match__winner__isnull=True
    ).aggregate(total=Sum("bet_amount"))["total"] or 0

    return render(request, 'core/model_detail.html', {
        'model': model,
        'predictions': predictions,
        'pending_bets': pending_bets,
        'display_balance': model.balance + pending_bets,
    })


def import_matches(request):
    import_matches_and_predictions.apply_async()
    return redirect('index')


def update_matches(request):
    update_matches_and_predictions.apply_async()
    return redirect('index')
