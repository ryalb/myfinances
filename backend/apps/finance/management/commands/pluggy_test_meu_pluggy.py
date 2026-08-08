import logging

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.finance.services import PluggyClient

logger = logging.getLogger(__name__)
User = get_user_model()


class Command(BaseCommand):
    help = "Testa a integração Pluggy Meu Pluggy e lista items para um usuário"

    def add_arguments(self, parser):
        parser.add_argument(
            "--user-id",
            type=int,
            help="ID do usuário para buscar items (default: primeiro usuário ativo)",
        )
        parser.add_argument(
            "--all-items",
            action="store_true",
            help="Não filtra por connectorId=200; mostra items de qualquer conector",
        )
        parser.add_argument(
            "--no-filter",
            action="store_true",
            help="Busca todos os items da aplicação e mostra o clientUserId de cada um",
        )
        parser.add_argument(
            "--diagnose",
            action="store_true",
            help="Executa diagnóstico completo: autenticação, aplicações, webhooks, items",
        )

    def handle(self, *args, **options):
        user_id = options.get("user_id")

        if user_id:
            try:
                user = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                self.stderr.write(f"Usuário ID {user_id} não encontrado.")
                return
        else:
            user = User.objects.filter(is_active=True).first()
            if not user:
                self.stderr.write("Nenhum usuário ativo encontrado.")
                return

        self.stdout.write(
            self.style.SUCCESS(
                f"Testando Pluggy Meu Pluggy para usuário: {user.email} (id={user.id})"
            )
        )

        client = PluggyClient(force_production=True)
        self.stdout.write(f"Base URL: {client.base_url}")
        self.stdout.write(f"Client ID: {client.client_id}")

        try:
            api_key = client._get_api_key()
            self.stdout.write(
                self.style.SUCCESS(f"[OK] Autenticação OK. API Key: {api_key[:4]}...")
            )
        except Exception as exc:
            self.stderr.write(f"[ERRO] Falha na autenticação: {exc}")
            return

        if options["diagnose"]:
            self._run_diagnose(client, user)
            return

        if options["no_filter"]:
            self._list_items(client, client_user_id=None, only_meu_pluggy=False)
            return

        self._list_items(
            client,
            client_user_id=str(user.id),
            only_meu_pluggy=not options["all_items"],
        )

    def _list_items(self, client, client_user_id, only_meu_pluggy):
        label = f"clientUserId={client_user_id}" if client_user_id else "todos (sem filtro)"
        self.stdout.write(f"\n--- Items: {label} ---")
        try:
            items = client.fetch_items(client_user_id=client_user_id)
        except Exception as exc:
            self.stderr.write(f"[ERRO] fetch_items falhou: {exc}")
            return

        if only_meu_pluggy:
            total = len(items)
            items = [it for it in items if client.is_meu_pluggy_item(it)]
            self.stdout.write(
                f"[INFO] {len(items)} de {total} items são do Meu Pluggy (connectorId=200)"
            )
        else:
            self.stdout.write(f"[INFO] {len(items)} items retornados")

        if not items:
            self.stdout.write(
                self.style.WARNING(
                    "Nenhum item. Rode com --no-filter para ver todos os items da "
                    "aplicação e conferir o clientUserId real de cada um."
                )
            )
            return

        for item in items:
            self._print_item(item)

    def _print_item(self, item):
        connector = item.get("connector") or {}
        self.stdout.write(
            f"  id={item.get('id')}\n"
            f"    connectorId={item.get('connectorId') or connector.get('id')}\n"
            f"    connectorName={connector.get('name')}\n"
            f"    status={item.get('status')} executionStatus={item.get('executionStatus')}\n"
            f"    clientUserId={item.get('clientUserId')}\n"
            f"    lastUpdatedAt={item.get('lastUpdatedAt')} "
            f"nextAutoSyncAt={item.get('nextAutoSyncAt')}"
        )

    def _run_diagnose(self, client, user):
        self.stdout.write(self.style.SUCCESS("\n=== DIAGNÓSTICO COMPLETO ==="))

        self._check_applications(client)
        self._check_webhooks(client)

        self.stdout.write("\n--- Connect token ---")
        try:
            token_data = client.create_connect_token(str(user.id))
            self.stdout.write(
                f"[OK] Connect token criado: accessToken={bool(token_data.get('accessToken'))}"
            )
        except Exception as exc:
            self.stderr.write(f"[ERRO] create_connect_token falhou: {exc}")

        self._list_items(client, client_user_id=str(user.id), only_meu_pluggy=True)
        self._list_items(client, client_user_id=None, only_meu_pluggy=False)

    def _check_applications(self, client):
        self.stdout.write("\n--- Aplicações ---")
        try:
            apps = client.fetch_applications()
        except Exception as exc:
            self.stderr.write(f"[ERRO] Não foi possível listar aplicações: {exc}")
            self.stdout.write(
                "Dica: confira no Dashboard da Pluggy se a aplicação existe e tem o "
                "conector 'Meu Pluggy' adicionado."
            )
            return

        if not apps:
            self.stdout.write(
                self.style.WARNING(
                    "Nenhuma aplicação retornada. Verifique no Dashboard se há "
                    "aplicações criadas para estas credenciais."
                )
            )
            return

        self.stdout.write(f"[INFO] {len(apps)} aplicações encontradas")
        for app in apps:
            self.stdout.write(
                f"  id={app.get('id')} name={app.get('name')} clientId={app.get('clientId')}"
            )

    def _check_webhooks(self, client):
        self.stdout.write("\n--- Webhooks ---")
        try:
            webhooks = client.list_webhooks()
        except Exception as exc:
            self.stderr.write(f"[ERRO] Não foi possível listar webhooks: {exc}")
            return

        if not webhooks:
            self.stdout.write(
                self.style.WARNING(
                    "Nenhum webhook registrado. Sem webhook não existe sincronização "
                    "automática: registre com `manage.py pluggy_register_webhook`."
                )
            )
            return

        self.stdout.write(f"[INFO] {len(webhooks)} webhooks registrados")
        for hook in webhooks:
            self.stdout.write(
                f"  id={hook.get('id')} event={hook.get('event')} url={hook.get('url')}"
            )
