import os

from django.core.management.base import BaseCommand

from apps.finance.services import PluggyClient


class Command(BaseCommand):
    help = (
        "Registra (ou lista) o webhook da aplicacao na Pluggy. Necessario para items "
        "criados fora do nosso widget, como os do Meu Pluggy, que nao passam pelo "
        "webhookUrl do connect_token."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            help="URL do webhook. Default: PLUGGY_WEBHOOK_URL do ambiente.",
        )
        parser.add_argument(
            "--event",
            default="all",
            help="Evento a registrar (default: all).",
        )
        parser.add_argument(
            "--list",
            action="store_true",
            help="Apenas lista os webhooks ja registrados.",
        )
        parser.add_argument(
            "--delete",
            metavar="WEBHOOK_ID",
            help="Remove o webhook com o ID informado.",
        )

    def handle(self, *args, **options):
        client = PluggyClient(force_production=True)
        self.stdout.write(f"Base URL: {client.base_url}")

        if options["delete"]:
            client.delete_webhook(options["delete"])
            self.stdout.write(self.style.SUCCESS(f"Webhook {options['delete']} removido."))
            return

        if options["list"]:
            self._list(client)
            return

        url = options["url"] or os.getenv("PLUGGY_WEBHOOK_URL", "")
        if not url:
            self.stderr.write(
                "Nenhuma URL informada. Passe --url ou defina PLUGGY_WEBHOOK_URL no .env."
            )
            return

        secret = os.getenv("PLUGGY_WEBHOOK_SECRET", "")
        if not secret:
            self.stderr.write(
                "PLUGGY_WEBHOOK_SECRET nao configurado. O endpoint vai rejeitar todas as "
                "entregas com HTTP 503 ate que ele exista."
            )
            return
        if f"token={secret}" not in url:
            self.stderr.write(
                "A URL nao contem ?token=<PLUGGY_WEBHOOK_SECRET>. Sem isso o endpoint "
                "responde 403 e a Pluggy desiste apos 9 tentativas."
            )
            return

        result = client.register_webhook(url, event=options["event"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Webhook registrado: id={result.get('id')} event={result.get('event')} "
                f"url={result.get('url')}"
            )
        )
        self._list(client)

    def _list(self, client):
        self.stdout.write("\n--- Webhooks registrados ---")
        webhooks = client.list_webhooks()
        if not webhooks:
            self.stdout.write(
                self.style.WARNING(
                    "Nenhum webhook registrado. Sem webhook nao ha sincronizacao automatica."
                )
            )
            return
        for hook in webhooks:
            self.stdout.write(
                f"  id={hook.get('id')} event={hook.get('event')} "
                f"url={hook.get('url')} createdAt={hook.get('createdAt')}"
            )
