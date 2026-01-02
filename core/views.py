import json
import datetime

from django.db.models import Sum, Q
from django.shortcuts import render, get_object_or_404, redirect

from .models import ModelAI, Match, Prediction, BalanceHistory
from .tasks import import_matches_and_predictions, update_matches_and_predictions


def index(request):
    models = ModelAI.objects.annotate(
        pending_bets=Sum(
            "predictions__bet_amount",
            filter=Q(predictions__result__isnull=True)
        )
    )

    models_with_pending = [
        {
            "id": m.id,
            "slug": m.slug,
            "name": m.name,
            "balance": m.balance,
            "pending_bets": m.pending_bets or 0,
            "display_balance": m.balance + (m.pending_bets or 0),
        }
        for m in models
    ]

    matches = Match.objects.all()

    last_completed_date = (
        Prediction.objects
        .filter(result__isnull=False)
        .order_by("-match__date")
        .values_list("match__date", flat=True)
        .first()
    )

    if last_completed_date:
        completed_bets = (
            Prediction.objects
            .filter(
                result__isnull=False,
                match__date=last_completed_date
            )
            .select_related("match", "ai_model")
            .order_by("-id")
        )
    else:
        completed_bets = Prediction.objects.none()

    upcoming_qs = (
        Prediction.objects
        .filter(
            result__isnull=True,
            match__date__gte=datetime.datetime.now().date()
        )
        .select_related("match", "ai_model")
        .order_by("match__date")
    )

    next_day = upcoming_qs.values_list("match__date", flat=True).first()

    upcoming_bets = (
        upcoming_qs.filter(match__date=next_day)
        if next_day else Prediction.objects.none()
    )

    history = (
        BalanceHistory.objects
        .select_related("ai_model")
        .order_by("date")
    )

    history_data = {}
    for h in history:
        history_data.setdefault(h.ai_model.name, []).append({
            "date": h.date.replace(hour=1).replace(minute=0).strftime("%Y-%m-%d %H:%M"),
            "balance": float(h.balance)
        })

    history_json = json.dumps(history_data)

    last_update = BalanceHistory.objects.last().date.replace(hour=1).replace(minute=0).replace(second=0)

    return render(request, "core/index.html", {
        "request": request,
        "models": models_with_pending,
        "matches": matches,
        "completed_bets": completed_bets,
        "upcoming_bets": upcoming_bets,
        "balance_history": history,
        "history_data": history_json,
        "last_update": last_update,
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
