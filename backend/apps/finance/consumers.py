import logging
import urllib.parse

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

logger = logging.getLogger(__name__)


class SyncConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = None
        self.group_name = None

        query_string = self.scope.get("query_string", b"").decode("utf-8")
        params = urllib.parse.parse_qs(query_string)
        token_value = params.get("token", [None])[0]

        if token_value:
            try:
                jwt_auth = JWTAuthentication()
                validated_token = jwt_auth.get_validated_token(token_value.encode())
                self.user = await database_sync_to_async(jwt_auth.get_user)(validated_token)
            except (InvalidToken, Exception):
                logger.warning("WebSocket authentication failed")

        if self.user is None:
            # O Daphne só entrega um close code customizado ao cliente se a
            # conexão já foi aceita: fechar antes do accept() faz o handshake
            # ser rejeitado com HTTP 403 genérico, e o navegador só vê code
            # 1006 (abnormal closure) — o 4001 nunca chegaria no front.
            await self.accept()
            await self.close(code=4001)
            return

        self.group_name = f"user_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def sync_event(self, event):
        await self.send_json(
            {
                "type": event["type"],
                "status": event["status"],
                "connection_id": event["connection_id"],
                "sync_job_id": event["sync_job_id"],
            }
        )
