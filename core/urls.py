from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('model/<slug:slug>/', views.model_detail, name='model_detail'),
    path('event/<int:event_id>/', views.event_detail, name='event_detail'),

    path('import/', views.import_matches, name='import_matches'),
    path('update/', views.update_matches, name='update_matches'),

    path('register/', views.register_view, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name="core/login.html"), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('profile/', views.profile_view, name='profile'),
]
