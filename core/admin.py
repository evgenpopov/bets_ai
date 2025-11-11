from django.contrib import admin
from .models import ModelAI, Match, Prediction, BalanceHistory


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('date', 'home', 'away', 'winner', 'type',)
    search_fields = ('home', 'away')
    list_filter = ('type', 'date')
    ordering = ('-date',)


@admin.register(ModelAI)
class ModelAIAdmin(admin.ModelAdmin):
    list_display = ('name', 'balance')
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ('ai_model', 'match', 'predicted_winner', 'bet_amount', 'odds', 'result')
    list_filter = ('ai_model', 'match__date')
    search_fields = ('ai_model__name', 'match__home', 'match__away')
    autocomplete_fields = ('ai_model', 'match')
    ordering = ('-match__date',)


@admin.register(BalanceHistory)
class BalanceHistoryAdmin(admin.ModelAdmin):
    list_display = ('ai_model', 'date', 'balance',)
    search_fields = ('ai_model__name',)
    list_filter = ('ai_model', 'date')
    ordering = ('-date',)
