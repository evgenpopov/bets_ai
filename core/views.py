from django.shortcuts import render, redirect
from .models import Fight, ModelAI, Prediction, BalanceHistory
from .utils import get_upcoming_fights
from .ai_models import ChatGPTModel, DeepSeekModel, GeminiModel


def index(request):
    models = ModelAI.objects.all()
    fights = Fight.objects.all()
    predictions = Prediction.objects.select_related("ai_model", "fight").all()
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
        "fights": fights,
        "predictions": predictions,
        "history_data": data,
        "balance_history": balance_history
    })


def run_predictions(request):
    if request.method == "POST":
        fights = get_upcoming_fights()
        ai_models = [ChatGPTModel(), DeepSeekModel(), GeminiModel()]

        for f in fights:
            fight, _ = Fight.objects.get_or_create(
                fighter1=f["fighter1"],
                fighter2=f["fighter2"],
                date=f["date"]
            )
            for model in ai_models:
                model_ai, _ = ModelAI.objects.get_or_create(name=model.name)
                pred, created = Prediction.objects.get_or_create(
                    ai_model=model_ai,
                    fight=fight,
                    predicted_winner=model.predict(f)
                )
                if created:
                    pred.evaluate()
        return redirect("index")
    return redirect("index")