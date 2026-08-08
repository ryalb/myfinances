from django.core.management.base import BaseCommand
from django.db import transaction as db_transaction

from apps.finance.models import Account, Card, Transaction


class Command(BaseCommand):
    help = (
        "Corrige contas de credito gravadas duas vezes: como Account e como Card. "
        "Antes do filtro `type=BANK` em sync_connection_data, `GET /accounts` sem "
        "filtro trazia as contas CREDIT, que viravam Account, e `fetch_item_cards` "
        "gravava as mesmas como Card. Isso conta o passivo em dobro no patrimonio. "
        "As transacoes da Account sao re-apontadas para o Card antes de remover a "
        "Account -- deletar direto faria CASCADE e apagaria as transacoes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Aplica as mudancas. Sem esta flag, apenas relata (dry-run).",
        )

    def handle(self, *args, **options):
        execute = options["execute"]

        cards_by_external_id = {c.external_id: c for c in Card.objects.all()}
        duplicates = list(Account.objects.filter(external_id__in=cards_by_external_id.keys()))

        if not duplicates:
            self.stdout.write(
                self.style.SUCCESS("Nada a corrigir: nenhuma Account duplica um Card.")
            )
            return

        self.stdout.write(self.style.WARNING(f"{len(duplicates)} Account(s) duplicando um Card:\n"))

        total_moved = 0
        for account in duplicates:
            card = cards_by_external_id[account.external_id]
            tx_count = Transaction.objects.filter(account=account).count()
            total_moved += tx_count
            self.stdout.write(
                f"  Account {account.external_id}\n"
                f"    nome:       {account.name}\n"
                f"    type:       {account.type}  saldo={account.balance}\n"
                f"    Card:       id={card.id} limite={card.credit_limit} "
                f"saldo={card.current_balance}\n"
                f"    transacoes: {tx_count} -> serao re-apontadas para o Card\n"
            )

        if not execute:
            self.stdout.write(
                self.style.WARNING(
                    f"DRY-RUN: nada foi alterado.\n"
                    f"Seriam re-apontadas {total_moved} transacoes e removidas "
                    f"{len(duplicates)} Account(s).\n"
                    f"Rode com --execute para aplicar."
                )
            )
            return

        with db_transaction.atomic():
            for account in duplicates:
                card = cards_by_external_id[account.external_id]
                moved = Transaction.objects.filter(account=account).update(account=None, card=card)
                remaining = Transaction.objects.filter(account=account).count()
                if remaining:
                    raise RuntimeError(
                        f"Abortado: {remaining} transacoes ainda ligadas a "
                        f"{account.external_id}; remover a Account causaria CASCADE."
                    )
                account.delete()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  OK {account.external_id}: {moved} transacoes movidas para o "
                        f"Card {card.id}, Account removida"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nConcluido: {total_moved} transacoes re-apontadas, "
                f"{len(duplicates)} Account(s) removida(s)."
            )
        )
        self.stdout.write(
            "Recalcule o patrimonio para refletir a correcao:\n"
            '  python manage.py shell -c "'
            "from django.contrib.auth import get_user_model; "
            "from apps.finance.consolidation import snapshot_net_worth; "
            '[snapshot_net_worth(u) for u in get_user_model().objects.all()]"'
        )
