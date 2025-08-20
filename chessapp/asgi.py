import os
import django
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application
import chessgame.routing  # 👈 Import your websocket routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chessapp.settings')
django.setup()

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            chessgame.routing.websocket_urlpatterns
        )
    ),
})
