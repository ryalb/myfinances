import logging
import os
import sys
from datetime import timedelta
from pathlib import Path

from celery.schedules import crontab
from dotenv import load_dotenv
from rich.console import Console
from rich.logging import RichHandler

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class FullWidthRichHandler(RichHandler):
    def __init__(self, *args, **kwargs):
        console = Console(
            width=200,
            force_terminal=True,
            stderr=True,
        )
        super().__init__(*args, console=console, **kwargs)


class StreamToLogger:
    def __init__(self, logger_name="stdout", level=logging.INFO):
        self.logger = logging.getLogger(logger_name)
        self.level = level
        self._sys_stdout = sys.__stdout__

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            cleaned = line.strip()
            if cleaned:
                self.logger.log(self.level, cleaned)

    def flush(self):
        pass

    def isatty(self):
        return getattr(self._sys_stdout, "isatty", lambda: False)()

    @property
    def encoding(self):
        return getattr(self._sys_stdout, "encoding", "utf-8")


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "unsafe-dev-key")
DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() == "true"

ALLOWED_HOSTS = [
    h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    "graphene_django",
    "channels",
    "django_gravatar",
    "apps.finance.apps.FinanceConfig",
]

GRAVATAR_DEFAULT_IMAGE = "identicon"

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # Antes de session/auth: rejeita o que vem do tunel publico o mais cedo possivel.
    "apps.finance.middleware.PublicTunnelRestrictionMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Hosts de tunel (ngrok/cloudflared). Requisicoes que chegarem por eles so podem
# alcancar PUBLIC_TUNNEL_ALLOWED_PATHS; todo o resto recebe 404.
# O tunel encaminha a porta inteira, entao sem isto expor o webhook expoe
# tambem /admin/, /graphql/ e /api/v1/auth/token/.
PUBLIC_TUNNEL_HOSTS = [
    h.strip() for h in os.getenv("DJANGO_PUBLIC_TUNNEL_HOSTS", "").split(",") if h.strip()
]

PUBLIC_TUNNEL_ALLOWED_PATHS = (
    "/api/v1/pluggy/webhook/",
    "/health/",
)

# Uso pessoal: o registro publico nasce desligado. Ligar permite que qualquer
# pessoa com acesso a API crie uma conta.
ALLOW_PUBLIC_REGISTRATION = os.getenv("DJANGO_ALLOW_PUBLIC_REGISTRATION", "False").lower() == "true"

# Categorias da Pluggy (provider_category, comparadas em minusculo) que sao
# dinheiro mudando de bolso do proprio usuario -- pagamento de fatura de cartao,
# transferencia entre contas proprias -- e nao renda nem gasto real. Sem excluir
# isso, o pagamento da fatura entra como receita no lado do cartao (a Pluggy manda
# type=CREDIT ali) e/ou como despesa duplicada no lado da conta, alem do gasto ja
# contado quando a compra foi feita no cartao.
FINANCE_INTERNAL_TRANSFER_CATEGORIES = [
    c.strip().lower()
    for c in os.getenv(
        "FINANCE_INTERNAL_TRANSFER_CATEGORIES",
        "credit card payment,"
        "same person transfer,same person transfer - cash,"
        "same person transfer - pix,same person transfer - ted,"
        "transfer - internal",
    ).split(",")
    if c.strip()
]

# Cenario de estresse do simulador de futuro financeiro (apps.finance.projections):
# queda de mercado unica + meses sem aporte, ambos no inicio do horizonte. Valores
# arbitrarios de produto, nao derivados de dado historico -- por isso configuraveis.
FINANCE_STRESS_MARKET_DROP_PCT = os.getenv("FINANCE_STRESS_MARKET_DROP_PCT", "20")
FINANCE_STRESS_INCOME_GAP_MONTHS = os.getenv("FINANCE_STRESS_INCOME_GAP_MONTHS", "3")

# Categorias de transacao (normalizadas, pt-BR -- ver domain.CATEGORY_KEYWORDS)
# tratadas como despesa fixa pelo otimizador de orcamento (apps.finance.budget_
# buckets). O resto do debito cai em discricionario por default. Assinaturas
# entram em despesas fixas por um caminho separado (Subscription), nao por
# categoria -- por isso nao aparecem aqui.
FINANCE_FIXED_EXPENSE_CATEGORIES = [
    c.strip()
    for c in os.getenv("FINANCE_FIXED_EXPENSE_CATEGORIES", "Moradia,Saúde,Educação").split(",")
    if c.strip()
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "myfinances"),
        "USER": os.getenv("POSTGRES_USER", "myfinances"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "myfinances"),
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        # Managed Postgres (Neon, Supabase) rejects plain connections, so this
        # defaults to "prefer" for local/Docker Postgres and must be set to
        # "require" via POSTGRES_SSLMODE for Neon.
        # connect_timeout: sem ele uma conexao que nao recebe resposta do
        # servidor (visto no Neon) trava o processo para sempre.
        "OPTIONS": {
            "sslmode": os.getenv("POSTGRES_SSLMODE", "prefer"),
            "connect_timeout": int(os.getenv("POSTGRES_CONNECT_TIMEOUT", "10")),
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/hour",
        "user": "2000/hour",
        # Tentativas de senha. O endpoint de token nao tinha limite nenhum.
        "login": "10/hour",
    },
}

# Default do SimpleJWT e 5min de access token -- curto demais para uso pessoal
# continuo (o app nao tem risco de sessao roubada que justifique isso). Refresh
# token continua no default (1 dia); sem ROTATE_REFRESH_TOKENS, o mesmo
# refresh token vale para todo o dia, reusado a cada renovacao.
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
}

GRAPHENE = {"SCHEMA": "config.schema.schema"}

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
]

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# O throttling do DRF guarda os contadores no cache. Com o LocMemCache default,
# eles sao por processo e se perdem no restart -- inutil como limite de tentativas
# de senha. O Redis ja e dependencia do Celery e dos channels.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# Precisa de `celery -A config beat` rodando (mise run backend-beat), senao
# nada aqui dispara. As tasks sao idempotentes por dia, entao um beat que ficou
# fora do ar so perde pontos do periodo -- reexecutar nao duplica nada.
CELERY_BEAT_SCHEDULE = {
    "snapshot-patrimonio-diario": {
        "task": "apps.finance.tasks.snapshot_all_users",
        # 03:10 local: depois da janela de auto-sync noturna da Pluggy, para o
        # snapshot pegar os saldos do dia anterior ja atualizados.
        "schedule": crontab(hour=3, minute=10),
    },
    "reconciliar-assinaturas-diario": {
        "task": "apps.finance.tasks.reconcile_all_subscriptions",
        "schedule": crontab(hour=3, minute=30),
    },
    "sincronizar-indices-mercado-diario": {
        "task": "apps.finance.tasks.sync_market_data",
        # Series do Bacen SGS costumam publicar o ponto do dia anterior de manha.
        "schedule": crontab(hour=6, minute=0),
    },
    "sincronizar-cotacoes-mercado-diario": {
        "task": "apps.finance.tasks.sync_market_quotes",
        "schedule": crontab(hour=6, minute=15),
    },
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
        },
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "rich": {
            "format": "%(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "config.settings.FullWidthRichHandler",
            "formatter": "rich",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.server": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "py.warnings": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}

logging.captureWarnings(True)

if "test" not in sys.argv:
    sys.stdout = StreamToLogger()
