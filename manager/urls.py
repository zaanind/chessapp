from django.urls import path
from .views import manager
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', manager, name='manager'),
    path('wallet/', views.manage_wallet_requests, name='manage_wallet_requests'),
    path('game/<int:game_id>/edit/', views.manage_game_room, name='manage_game_room'),
    path('add-user/', views.add_user_view, name='add_user_platform'),
    path('users/', views.user_list_view, name='user_list'),
    path('commissions/', views.company_commission_list, name='company_commission_list'),

    

    
]
 