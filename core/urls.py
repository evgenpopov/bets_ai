from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('model/<int:model_id>/', views.model_detail, name='model_detail'),
]
