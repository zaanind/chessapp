from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path("ws/chess/<str:room_id>/", consumers.ChessConsumer.as_asgi()),
    path("ws/home/", consumers.Online_check_landing_Consumer.as_asgi()),
]
