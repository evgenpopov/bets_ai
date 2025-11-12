import json
from django.db.models import Sum, OuterRef, Subquery
from django.shortcuts import render, get_object_or_404, redirect

from .models import ModelAI, Match, Prediction, BalanceHistory
from .utils import get_model_prediction, get_match_odds


def index(request):
    models = ModelAI.objects.all()
    matches = Match.objects.all()
    latest_preds = Prediction.objects.filter(
        ai_model=OuterRef('ai_model')
    ).order_by('-match__date')

    predictions = Prediction.objects.filter(
        id__in=Subquery(latest_preds.values('id')[:3])
    )
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
        "models": models_with_pending,
        "matches": matches,
        "predictions": predictions,
        "balance_history": balance_history,
        "history_data": data,
    })


def model_detail(request, slug):
    model = get_object_or_404(ModelAI, slug=slug)
    predictions = model.predictions.select_related('match').order_by('-match__date')

    pending_bets = model.predictions.filter(
        match__winner__isnull=True
    ).aggregate(total=Sum("bet_amount"))["total"] or 0

    display_balance = model.balance + pending_bets

    return render(request, 'core/model_detail.html', {
        'model': model,
        'predictions': predictions,
        'pending_bets': pending_bets,
        'display_balance': display_balance,
    })



def make_bets(request):
    matches = Match.objects.filter(winner__isnull=True)
    model = ModelAI.objects.get(name="ChatGPT 4")  # make qs of all models

    for match in matches:
        odds_data = get_match_odds(match.home, match.away)
        data = {
            "balance": model.balance, "home": match.home, "away": match.away,
            "date": match.date.strftime("%Y-%m-%d"),
            "home_last_results": match.metadata_home[:3] if match.metadata_home else "",
            "away_last_results": match.metadata_away[:3] if match.metadata_away else "",
            "home_rate": odds_data.get(match.home, "None"),
            "draw_rate": odds_data.get("Draw", "None"),
            "away_rate": odds_data.get(match.away, "None"),
        }
        prediction_data = json.loads(get_model_prediction(data))
        prediction_result = prediction_data.get("result")
        prediction_stake = prediction_data.get("stake")
        Prediction.objects.create(
            ai_model=model,
            match=match,
            predicted_winner=prediction_result,
            bet_amount=prediction_stake,
            odds=odds_data.get(prediction_result, 1.5),
        )
        model.balance -= float(prediction_stake)
        print(model.balance)
        model.save()

    return redirect('index')
