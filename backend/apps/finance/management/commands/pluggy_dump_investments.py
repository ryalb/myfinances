"""Dump dos investimentos que a Pluggy devolve para uma conexao.

Existe porque a previdencia da Rico nao apareceu mesmo depois de corrigir o filtro
para `type: SECURITY`, e adivinhar o payload de novo seria repetir o erro. O comando
mostra `type`/`subtype`/`name` crus e diz, para cada item, se o filtro atual o
classificaria como previdencia.
"""

import json

from django.core.management.base import BaseCommand

from apps.finance.models import Connection
from apps.finance.services import PluggyClient
from apps.finance.tasks import _is_pension_investment, _is_withdrawn_investment


class Command(BaseCommand):
    help = "Mostra os investimentos crus que a Pluggy devolve para cada conexão"

    def add_arguments(self, parser):
        parser.add_argument(
            "--connection",
            help="external_id (itemId) de uma conexão específica. Sem isto, percorre todas.",
        )
        parser.add_argument(
            "--raw",
            action="store_true",
            help="Imprime o JSON completo de cada investimento.",
        )

    def handle(self, *args, **options):
        connections = Connection.objects.select_related("institution", "user").order_by("id")
        if options["connection"]:
            connections = connections.filter(external_id=options["connection"])

        if not connections.exists():
            self.stderr.write(self.style.ERROR("Nenhuma conexão encontrada."))
            return

        client = PluggyClient()
        for connection in connections:
            self.stdout.write("")
            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    f"{connection.institution.name} (item {connection.external_id})"
                )
            )
            try:
                investments = client.fetch_item_investments(connection.external_id)
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"  falha ao buscar investimentos: {exc}"))
                continue

            if not investments:
                self.stdout.write("  (a Pluggy não devolveu investimento nenhum)")
                continue

            for investment in investments:
                if _is_pension_investment(investment):
                    marker = self.style.SUCCESS("PREVIDÊNCIA")
                elif _is_withdrawn_investment(investment):
                    marker = self.style.WARNING("LIQUIDADO")
                else:
                    marker = "investimento"
                self.stdout.write(
                    f"  [{marker}] type={investment.get('type')!r} "
                    f"subtype={investment.get('subtype')!r} "
                    f"status={investment.get('status')!r} "
                    f"name={investment.get('name')!r} "
                    f"balance={investment.get('balance')!r}"
                )
                if options["raw"]:
                    self.stdout.write(json.dumps(investment, indent=2, ensure_ascii=False))
