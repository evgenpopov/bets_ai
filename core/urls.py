from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('model/<slug:slug>/', views.model_detail, name='model_detail'),
    path('event/<int:event_id>/', views.event_detail, name='event_detail'),
    path('import_matches/', views.import_matches, name='import_matches'),
    path('update_matches/', views.update_matches, name='update_matches'),
]
