import os

from django.core.asgi import get_asgi_application

from config.boot import run_pending_migrations

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django_asgi_app = get_asgi_application()

run_pending_migrations()

from channels.routing import ProtocolTypeRouter, URLRouter

from apps.finance.routing import websocket_urlpatterns

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": URLRouter(websocket_urlpatterns),
    }
)
