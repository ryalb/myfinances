from django.core.management.base import BaseCommand

from apps.finance.market_data import sync_market_quotes_for_held_tickers


class Command(BaseCommand):
    help = (
        "Busca no brapi.dev a cotacao mais recente dos tickers que aparecem em "
        "algum Investment.code e grava em MarketQuote."
    )

    def handle(self, *args, **options):
        count = sync_market_quotes_for_held_tickers()
        self.stdout.write(self.style.SUCCESS(f"{count} cotacoes sincronizadas"))
