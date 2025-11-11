from django.shortcuts import render, get_object_or_404

from .models import ModelAI, Match, Prediction, BalanceHistory


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
