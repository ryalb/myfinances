from django.core.management.base import BaseCommand

from apps.finance.domain import refine_connection_institution
from apps.finance.models import Connection


class Command(BaseCommand):
    help = (
        "Re-deriva a instituicao de cada conexao a partir dos nomes das contas e "
        "cartoes ja sincronizados. Items do Meu Pluggy chegam todos como "
        "connectorId=200 / 'MeuPluggy', entao sem isto a UI mostra cards identicos.\n\n"
        "Idempotente: rode sempre que o nome de uma conexao aparecer como "
        "'MeuPluggy' em vez do banco real, sem precisar re-sincronizar."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Mostra o que mudaria sem gravar.",
        )
        parser.add_argument(
            "--user-id",
            type=int,
            help="Restringe a um usuario.",
        )

    def handle(self, *args, **options):
        connections = Connection.objects.select_related("institution").order_by("id")
        if options["user_id"]:
            connections = connections.filter(user_id=options["user_id"])

        connections = list(connections)
        if not connections:
            self.stdout.write("Nenhuma conexao encontrada.")
            return

        changed = 0
        skipped = 0
        for connection in connections:
            before = connection.institution.name if connection.institution_id else None
            before_pid = connection.institution.provider_id if connection.institution_id else None

            accounts = list(connection.accounts.values_list("name", flat=True))
            cards = list(connection.cards.values_list("name", flat=True))

            self.stdout.write(f"{connection.external_id}")
            self.stdout.write(f"   atual:  {before!r} ({before_pid!r})")
            self.stdout.write(f"   fontes: contas={accounts} cartoes={cards}")

            if not accounts and not cards:
                self.stdout.write(
                    self.style.WARNING("   sem contas nem cartoes: sincronize antes de derivar\n")
                )
                skipped += 1
                continue

            if options["dry_run"]:
                from apps.finance.domain import derive_institution_from_names

                derived = derive_institution_from_names(accounts + cards)
                target = derived[1] if derived else "(fallback pelo nome da conta)"
                self.stdout.write(f"   [dry-run] derivaria: {target}\n")
                continue

            institution = refine_connection_institution(connection)
            if institution is None:
                self.stdout.write(self.style.WARNING("   nao foi possivel derivar\n"))
                skipped += 1
                continue

            if institution.name != before:
                changed += 1
                self.stdout.write(
                    self.style.SUCCESS(f"   -> {institution.name!r} ({institution.provider_id})\n")
                )
            else:
                self.stdout.write("   sem mudanca\n")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("DRY-RUN: nada foi gravado."))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Concluido: {changed} conexao(oes) atualizada(s), {skipped} sem alteracao."
            )
        )
