import logging

from django.conf import settings
from django.http import HttpResponseNotFound

logger = logging.getLogger(__name__)


class PublicTunnelRestrictionMiddleware:
    """Restrict what a public tunnel host can reach.

    Um tunel (ngrok/cloudflared) encaminha a porta inteira, nao um path. Sem isto,
    expor o webhook da Pluggy expoe tambem `/admin/`, `/graphql/`,
    `/api/v1/auth/token/` e o registro publico -- com tracebacks completos se
    DEBUG=True.

    Requisicoes que chegam por um host listado em `PUBLIC_TUNNEL_HOSTS` so passam
    se o path estiver em `PUBLIC_TUNNEL_ALLOWED_PATHS`. O resto recebe 404 (nao
    403: um 403 confirmaria que existe algo ali). Acesso por localhost nao e
    afetado.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Lido por requisicao, nao no __init__: a cadeia de middleware e construida
        # uma vez, entao cachear aqui exigiria restart para mudar a config (e
        # tornaria isto intestavel com override de settings).
        tunnel_hosts = {
            h.strip().lower()
            for h in getattr(settings, "PUBLIC_TUNNEL_HOSTS", [])
            if h and h.strip()
        }
        if tunnel_hosts:
            allowed_paths = tuple(getattr(settings, "PUBLIC_TUNNEL_ALLOWED_PATHS", ()))
            host = request.get_host().split(":")[0].lower()
            if host in tunnel_hosts and not request.path.startswith(allowed_paths):
                logger.warning(
                    "Blocked tunnel request: host=%s path=%s method=%s remote=%s",
                    host,
                    request.path,
                    request.method,
                    request.META.get("REMOTE_ADDR"),
                )
                return HttpResponseNotFound()
        return self.get_response(request)
