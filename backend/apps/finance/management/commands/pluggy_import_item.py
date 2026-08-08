from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction as db_transaction

from apps.finance.domain import get_or_create_institution
from apps.finance.models import (
    Connection,
    ConnectionStatus,
    NetWorthSnapshot,
    ProcessedWebhookEvent,
    SyncJob,
)
from apps.finance.services import PluggyClient
from apps.finance.tasks import sync_connection_data


class Command(BaseCommand):
    help = (
        "Importa items da Pluggy por itemId e sincroniza. Use isto em vez de "
        "/pluggy/discover/: a Pluggy nao expoe listagem de items (GET /items "
        "responde 401), so a busca individual (GET /items/{id}). O itemId vem do "
        "Dashboard da Pluggy ou do payload do webhook.\n\n"
        "Cada conexao do Meu Pluggy e um item separado -- a tela de consentimento "
        "permite escolher uma conexao por autorizacao. Passe --item uma vez por item."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--item",
            action="append",
            dest="items",
            metavar="ITEM_ID",
            help="itemId da Pluggy. Repita a flag para varios items.",
        )
        parser.add_argument(
            "--user-id",
            type=int,
            help="ID do usuario dono das conexoes.",
        )
        parser.add_argument(
            "--email",
            help="Email do usuario dono das conexoes (alternativa a --user-id).",
        )
        parser.add_argument(
            "--claim",
            action="store_true",
            help=(
                "Transfere para o usuario informado items que hoje pertencem a outro. "
                "Disponivel so na CLI: o endpoint HTTP nunca reatribui posse."
            ),
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help=(
                "APAGA os dados derivados da Pluggy do usuario (conexoes, contas, "
                "cartoes, transacoes, investimentos, snapshots) antes de importar. "
                "Exige --yes."
            ),
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Confirma o --reset sem prompt.",
        )
        parser.add_argument(
            "--async",
            action="store_true",
            dest="run_async",
            help="Enfileira o sync no Celery em vez de rodar inline.",
        )

    def handle(self, *args, **options):
        item_ids = options["items"] or []
        if not item_ids:
            raise CommandError(
                "Informe ao menos um --item ITEM_ID.\n"
                "Os itemIds aparecem no Dashboard da Pluggy, em Itens Conectados."
            )

        user = self._resolve_user(options)
        self.stdout.write(f"Usuario: {user.email or user.username} (id={user.id})")

        if options["reset"]:
            if not options["yes"]:
                raise CommandError(
                    "--reset apaga dados financeiros. Confirme com --yes.\n"
                    "Faca backup antes: mise run db-backup"
                )
            self._reset(user)

        client = PluggyClient(force_production=True)
        self.stdout.write(f"Base URL: {client.base_url}\n")

        for item_id in item_ids:
            self._import_item(
                client,
                user,
                item_id,
                run_async=options["run_async"],
                claim=options["claim"],
            )

    def _resolve_user(self, options):
        """Resolve o usuario alvo sem adivinhar.

        Escolher "o primeiro usuario ativo" ja vinculou dados financeiros a uma
        conta de teste em vez da conta real.
        """
        User = get_user_model()

        if options["user_id"]:
            try:
                return User.objects.get(pk=options["user_id"])
            except User.DoesNotExist as exc:
                raise CommandError(f"Usuario id={options['user_id']} nao encontrado.") from exc

        if options["email"]:
            matches = list(User.objects.filter(email__iexact=options["email"]))
            if not matches:
                matches = list(User.objects.filter(username__iexact=options["email"]))
            if not matches:
                raise CommandError(f"Nenhum usuario com email/username {options['email']!r}.")
            if len(matches) > 1:
                raise CommandError(
                    f"{len(matches)} usuarios com esse email. Use --user-id: "
                    + ", ".join(f"{u.id}={u.email or u.username}" for u in matches)
                )
            return matches[0]

        candidates = list(User.objects.filter(is_active=True).order_by("id"))
        if not candidates:
            raise CommandError("Nenhum usuario ativo encontrado.")
        if len(candidates) > 1:
            listing = "\n".join(f"  --user-id {u.id}   {u.email or u.username}" for u in candidates)
            raise CommandError(
                "Existe mais de um usuario ativo; informe explicitamente qual e o dono.\n"
                "Vincular as contas ao usuario errado causa 409 ao importar pela UI.\n"
                f"{listing}\n\n"
                "Dica: para saber com qual usuario voce esta logado no frontend, "
                "chame GET /api/v1/me/ com o seu token."
            )
        return candidates[0]

    def _reset(self, user) -> None:
        self.stdout.write(self.style.WARNING("\n--- RESET ---"))
        with db_transaction.atomic():
            connections = Connection.objects.filter(user=user)
            self.stdout.write(f"  conexoes a remover: {connections.count()}")
            deleted, per_model = connections.delete()
            for model, count in sorted(per_model.items()):
                if count:
                    self.stdout.write(f"    {model}: {count}")

            snaps, _ = NetWorthSnapshot.objects.filter(user=user).delete()
            self.stdout.write(f"    snapshots de patrimonio: {snaps}")

            events, _ = ProcessedWebhookEvent.objects.all().delete()
            self.stdout.write(f"    eventos de webhook processados: {events}")
        self.stdout.write(
            self.style.SUCCESS(f"  total de registros removidos: {deleted + snaps + events}\n")
        )

    def _import_item(
        self, client, user, item_id: str, run_async: bool, claim: bool = False
    ) -> None:
        self.stdout.write(f"--- item {item_id} ---")
        try:
            item_data = client.fetch_item(item_id)
        except Exception as exc:
            self.stderr.write(f"  [ERRO] GET /items/{item_id} falhou: {exc}")
            return

        status = item_data.get("status", "")
        execution_status = item_data.get("executionStatus", "")
        connector = item_data.get("connector") or {}
        connector_id = item_data.get("connectorId") or connector.get("id")
        self.stdout.write(
            f"  connector={connector.get('name')} (id={connector_id})\n"
            f"  status={status} executionStatus={execution_status}\n"
            f"  clientUserId={item_data.get('clientUserId')}"
        )

        if status != "UPDATED":
            self.stdout.write(
                self.style.WARNING(
                    "  item nao esta UPDATED; a sincronizacao pode vir vazia ou parcial."
                )
            )

        institution = get_or_create_institution(item_data)
        connection, created = Connection.objects.get_or_create(
            external_id=str(item_id),
            defaults={
                "user": user,
                "institution": institution,
                "status": (
                    ConnectionStatus.ACTIVE if status == "UPDATED" else ConnectionStatus.PENDING
                ),
            },
        )
        if not created and connection.user_id != user.id:
            previous_owner = connection.user_id
            if not claim:
                self.stderr.write(
                    f"  [ERRO] item pertence ao usuario id={previous_owner}; "
                    f"nao vou reatribuir sem --claim.\n"
                    f"          Este e o mesmo motivo do 409 ao importar pela UI."
                )
                return
            connection.user = user
            connection.save(update_fields=["user", "updated_at"])
            self.stdout.write(
                self.style.WARNING(
                    f"  posse transferida do usuario id={previous_owner} para id={user.id}"
                )
            )

        self.stdout.write(
            f"  conexao {'criada' if created else 'existente'}: id={connection.id} "
            f"instituicao={institution.name}"
        )

        sync_job = SyncJob.objects.create(connection=connection, kind="full")
        if run_async:
            sync_connection_data.delay(sync_job.id)
            self.stdout.write(f"  sync enfileirado (SyncJob {sync_job.id})\n")
            return

        try:
            sync_connection_data(sync_job.id)
        except Exception as exc:
            self.stderr.write(f"  [ERRO] sync falhou: {exc}")
            return

        sync_job.refresh_from_db()
        connection.refresh_from_db()
        self.stdout.write(
            self.style.SUCCESS(
                f"  sync {sync_job.status}: contas={connection.accounts.count()} "
                f"cartoes={connection.cards.count()} "
                f"investimentos={connection.investments.count()}\n"
            )
        )
