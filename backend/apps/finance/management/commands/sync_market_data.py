from django.core.management.base import BaseCommand, CommandError

from apps.finance.market_data import (
    import_market_index_rates_from_file,
    sync_market_index_rates,
)
from apps.finance.models import MarketIndexKind


class Command(BaseCommand):
    help = (
        "Busca as taxas mais recentes de Selic, CDI e IPCA no Bacen SGS e grava "
        "em MarketIndexRate. Precisa de acesso a api.bcb.gov.br; use --from-file "
        "para importar um JSON ja baixado quando a rede da maquina bloquear isso."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--lookback-days",
            type=int,
            default=30,
            help="Quantos dias no passado buscar (default: 30). Ignorado com --from-file.",
        )
        parser.add_argument(
            "--from-file",
            help=(
                "Caminho de um JSON no formato da API do Bacen SGS "
                "(https://api.bcb.gov.br/dados/serie/bcdata.sgs.<id>/dados?formato=json), "
                "para importar sem acessar a rede."
            ),
        )
        parser.add_argument(
            "--kind",
            choices=[kind.value for kind in MarketIndexKind],
            help="Indice do arquivo informado em --from-file (obrigatorio junto com ele).",
        )

    def handle(self, *args, **options):
        from_file = options["from_file"]
        if from_file:
            kind_value = options["kind"]
            if not kind_value:
                raise CommandError("--kind e obrigatorio junto com --from-file.")
            count = import_market_index_rates_from_file(MarketIndexKind(kind_value), from_file)
            self.stdout.write(
                self.style.SUCCESS(f"{kind_value}: {count} pontos importados de {from_file}")
            )
            return

        synced = sync_market_index_rates(lookback_days=options["lookback_days"])
        for kind, count in synced.items():
            self.stdout.write(self.style.SUCCESS(f"{kind}: {count} pontos sincronizados"))
