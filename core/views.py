from django.shortcuts import render, get_object_or_404, redirect

from .models import ModelAI, Match, Prediction, BalanceHistory
from .utils import get_model_prediction, get_match_odds


def index(request):
    models = ModelAI.objects.all()
    matches = Match.objects.all()
    predictions = Prediction.objects.select_related("ai_model", "match").all()[:10]
    balance_history = BalanceHistory.objects.select_related("ai_model").order_by("-date")
    history = BalanceHistory.objects.order_by("date")
    data = {}
    for h in history:
        data.setdefault(h.ai_model.name, []).append({
            "date": h.date.strftime("%Y-%m-%d %H:%M"),
            "balance": h.balance
        })

    return render(request, "core/index.html", {
        "models": models,
        "matches": matches,
        "predictions": predictions,
        "balance_history": balance_history,
        "history_data": data,
    })


def model_detail(request, model_id):
    model = get_object_or_404(ModelAI, id=model_id)
    predictions = model.predictions.select_related('match').order_by('-match__date')

    return render(request, 'core/model_detail.html', {
        'model': model,
        'predictions': predictions,
    })


def make_bets(request):
    matches = Match.objects.filter(winner__isnull=True)

    for match in matches:
        print(match)
        odds_data = get_match_odds(match.home, match.away)
        prediction_data = get_model_prediction()

        # Prediction.objects.create(
        #     ai_model=model,
        #     match=match,
        #     predicted_winner=predicted_winner,
        #     bet_amount=bet_amount,
        #     odds=odds,
        # )

    return redirect('index')
