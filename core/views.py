from django.db.models import Sum, OuterRef, Subquery
from django.shortcuts import render, get_object_or_404, redirect

from .models import ModelAI, Match, Prediction, BalanceHistory
from .tasks import import_matches_and_predictions, update_matches_and_predictions


def index(request):
    models = ModelAI.objects.all()
    matches = Match.objects.all()
    latest_preds = Prediction.objects.filter(
        ai_model=OuterRef('ai_model')
    ).order_by('-id')

    predictions = Prediction.objects.filter(
        id__in=Subquery(latest_preds.values('id')[:3])
    ).order_by('-id')
    balance_history = BalanceHistory.objects.select_related("ai_model").order_by("-date")
    history = BalanceHistory.objects.order_by("date")
    data = {}
    for h in history:
        data.setdefault(h.ai_model.name, []).append({
            "date": h.date.strftime("%Y-%m-%d %H:%M"),
            "balance": h.balance
        })

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
        "predictions": predictions,
        "balance_history": balance_history,
        "history_data": data,
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
    import_matches_and_predictions.delay()
    return redirect('index')


def update_matches(request):
    update_matches_and_predictions.delay()
    return redirect('index')
