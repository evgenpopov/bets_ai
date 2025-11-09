from django.contrib import admin
from .models import Fight, ModelAI, Prediction, BalanceHistory


@admin.register(Fight)
class FightAdmin(admin.ModelAdmin):
    list_display = ('fighter1', 'fighter2', 'winner', 'date')
    search_fields = ('fighter1', 'fighter2')
    list_filter = ('date',)


@admin.register(ModelAI)
class ModelAIAdmin(admin.ModelAdmin):
    list_display = ('name', 'balance')
    search_fields = ('name',)


@admin.register(BalanceHistory)
class BalanceHistoryAdmin(admin.ModelAdmin):
    list_display = ('ai_model', 'date', 'balance')


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ('ai_model', 'fight', 'predicted_winner', 'bet_amount', 'result')
    list_filter = ('ai_model',)
    search_fields = ('fight__fighter1', 'fight__fighter2', 'ai_model__name')
    autocomplete_fields = ('ai_model', 'fight')
