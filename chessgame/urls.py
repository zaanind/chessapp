from django.urls import path
from .views import (chessboard_view, 
                  create_game_view,watch_game_view,
                  create_tournament_view,
                  participate_tournament_view,
                  suggest_tournament_fill)
from . import views

urlpatterns = [
    path('', create_game_view, name='create_game'),
    path('create/tournament', create_tournament_view, name='create_tournament'),
    path('play/<int:room_id>/', chessboard_view, name='chessboard'),
    path('watch/<int:room_id>/', watch_game_view, name='chessboard_watch'),
    path('join/tournament/<int:room_id>/', participate_tournament_view, name='participate_tournament'),
    path('tournament/suggest_fill/', suggest_tournament_fill, name='suggest_tournament_fill'),
    path('room/pairings/', views.room_pairings_view, name='room_pairings'),
    path('api/search-users/', views.api_search_users, name='api_search_users'),
    path('notifications/<int:notif_id>/redirect/', views.notification_redirect_view, name='notification_redirect'),

]
