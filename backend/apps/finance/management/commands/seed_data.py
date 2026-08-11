import random

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from faker import Faker

from apps.finance.models import (
    Account,
    AccountType,
    Card,
    CategorizationRule,
    Connection,
    ConnectionStatus,
    DocumentChunk,
    DocumentChunkStatus,
    Embedding,
    FinancialGoal,
    FinancialInstitution,
    GoalStatus,
    Investment,
    InvestmentPosition,
    NetWorthSnapshot,
    PensionPlan,
    Subscription,
    SubscriptionCategory,
    SubscriptionPayment,
    SubscriptionStatus,
    SyncJob,
    SyncJobStatus,
    Transaction,
    TransactionType,
)

User = get_user_model()
fake = Faker("pt_BR")


class Command(BaseCommand):
    help = "Limpa o banco e insere dados fake para teste local"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Não pede confirmação antes de limpar os dados",
        )
        parser.add_argument(
            "--noinput",
            action="store_true",
            help="Alias para --force",
        )

    def handle(self, *args, **options):
        force = options["force"] or options["noinput"]

        if not force:
            confirm = input("Isso irá apagar TODOS os dados do banco. Continuar? [s/N]: ")
            if confirm.lower() != "s":
                self.stdout.write("Operação cancelada.")
                return

        with transaction.atomic():
            self.stdout.write("Limpando dados existentes...")
            self._delete_all()

            self.stdout.write("Inserindo dados fake...")
            self._seed_data()

        self.stdout.write(self.style.SUCCESS("Dados fake inseridos com sucesso!"))

    def _delete_all(self):
        Embedding.objects.all().delete()
        DocumentChunk.objects.all().delete()
        SubscriptionPayment.objects.all().delete()
        Transaction.objects.all().delete()
        InvestmentPosition.objects.all().delete()
        SyncJob.objects.all().delete()
        PensionPlan.objects.all().delete()
        Investment.objects.all().delete()
        Subscription.objects.all().delete()
        CategorizationRule.objects.all().delete()
        NetWorthSnapshot.objects.all().delete()
        FinancialGoal.objects.all().delete()
        Card.objects.all().delete()
        Account.objects.all().delete()
        Connection.objects.all().delete()
        FinancialInstitution.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()

    def _seed_data(self):
        users = self._create_users(3)
        institutions = self._create_institutions()

        for user in users:
            connections = self._create_connections(user, institutions[: random.randint(2, 3)])

            for connection in connections:
                accounts = self._create_accounts(connection)
                cards = self._create_cards(connection)
                self._create_transactions(user, accounts, cards)
                self._create_investments(connection)
                self._create_pension_plans(connection)
                self._create_sync_jobs(connection)

            self._create_goals(user)
            self._create_net_worth_snapshots(user)
            self._create_subscriptions(user, accounts)
            self._create_categorization_rules(user)
            self._create_document_chunks(user)

    def _create_users(self, count):
        users = []
        for _ in range(count):
            user = User.objects.create_user(
                username=fake.user_name(),
                email=fake.email(),
                password="teste123",
                first_name=fake.first_name(),
                last_name=fake.last_name(),
            )
            users.append(user)
        return users

    def _create_institutions(self):
        names = ["Nubank", "Itaú", "Bradesco", "Banco do Brasil", "Inter", "C6 Bank"]
        institutions = []
        for name in names:
            institution = FinancialInstitution.objects.create(
                name=name,
                provider_id=fake.uuid4()[:8],
                logo_url=f"https://logo.clearbit.com/{name.lower().replace(' ', '')}.com",
            )
            institutions.append(institution)
        return institutions

    def _create_connections(self, user, institutions):
        connections = []
        for institution in institutions:
            status = random.choice(list(ConnectionStatus.choices))[0]
            connection = Connection.objects.create(
                user=user,
                institution=institution,
                external_id=fake.uuid4(),
                status=status,
                last_synced_at=timezone.now() if status == ConnectionStatus.ACTIVE else None,
                error_message=fake.sentence() if status == ConnectionStatus.ERROR else "",
            )
            connections.append(connection)
        return connections

    def _create_accounts(self, connection):
        accounts = []
        account_types = [
            AccountType.CHECKING,
            AccountType.SAVINGS,
            AccountType.BROKERAGE,
            AccountType.OTHER,
        ]
        for _ in range(random.randint(2, 4)):
            account_type = random.choice(account_types)
            balance = round(random.uniform(100, 50000), 2)
            account = Account.objects.create(
                connection=connection,
                external_id=fake.uuid4()[:12],
                name=fake.word().capitalize() + " " + account_type.label,
                type=account_type,
                currency="BRL",
                balance=balance,
                available_balance=round(balance * random.uniform(0.8, 1.0), 2),
            )
            accounts.append(account)
        return accounts

    def _create_cards(self, connection):
        cards = []
        for _ in range(random.randint(1, 2)):
            card = Card.objects.create(
                connection=connection,
                external_id=fake.uuid4()[:12],
                name=f"Cartão {fake.word().capitalize()}",
                last4=fake.numerify("####"),
                credit_limit=round(random.uniform(1000, 10000), 2),
                current_balance=round(random.uniform(0, 5000), 2),
                due_day=random.randint(1, 28),
                close_day=random.randint(1, 28),
            )
            cards.append(card)
        return cards

    def _create_transactions(self, user, accounts, cards):
        for _ in range(random.randint(20, 50)):
            account = random.choice(accounts) if accounts else None
            card = random.choice(cards) if cards else None

            if not account and not card:
                continue

            txn_type = random.choice(list(TransactionType.choices))[0]
            amount = round(random.uniform(5, 2000), 2)
            if txn_type == TransactionType.CREDIT:
                amount = abs(amount)
            else:
                amount = -abs(amount)

            booked_at = timezone.now() - timezone.timedelta(
                days=random.randint(0, 90),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59),
            )

            categories = [
                "Alimentação",
                "Transporte",
                "Saúde",
                "Educação",
                "Lazer",
                "Moradia",
                "Salário",
                "Investimentos",
                "Outros",
            ]

            Transaction.objects.create(
                account=account,
                card=card,
                external_id=fake.uuid4()[:16],
                description=fake.sentence(nb_words=4)[:500],
                amount=amount,
                currency="BRL",
                type=txn_type,
                category=random.choice(categories),
                provider_category=random.choice(categories),
                booked_at=booked_at,
            )

    def _create_investments(self, connection):
        kinds = ["CDB", "LCI", "LCA", "Fundos", "Ações", "Tesouro Direto"]
        for _ in range(random.randint(1, 3)):
            investment = Investment.objects.create(
                connection=connection,
                external_id=fake.uuid4()[:12],
                name=f"{random.choice(kinds)} {fake.word().capitalize()}",
                kind=random.choice(kinds),
                currency="BRL",
            )
            for _ in range(random.randint(1, 4)):
                as_of_date = timezone.now().date() - timezone.timedelta(days=random.randint(0, 180))
                quantity = round(random.uniform(0.1, 1000), 8)
                unit_price = round(random.uniform(1, 500), 8)
                InvestmentPosition.objects.create(
                    investment=investment,
                    as_of_date=as_of_date,
                    quantity=quantity,
                    unit_price=unit_price,
                    market_value=round(quantity * unit_price, 2),
                )

    def _create_pension_plans(self, connection):
        for _ in range(random.randint(0, 2)):
            PensionPlan.objects.create(
                connection=connection,
                user=connection.user,
                name=fake.word().capitalize() + " Prev",
                provider=fake.company(),
                balance=round(random.uniform(1000, 100000), 2),
            )

    def _create_sync_jobs(self, connection):
        for _ in range(random.randint(1, 3)):
            status = random.choice(list(SyncJobStatus.choices))[0]
            started_at = timezone.now() - timezone.timedelta(hours=random.randint(1, 48))
            finished_at = started_at + timezone.timedelta(minutes=random.randint(5, 60))
            SyncJob.objects.create(
                connection=connection,
                kind=random.choice(["full", "partial"]),
                status=status,
                started_at=started_at,
                finished_at=finished_at if status != SyncJobStatus.QUEUED else None,
                error_message=fake.sentence() if status == SyncJobStatus.FAILED else "",
            )

    def _create_goals(self, user):
        goal_names = [
            "Reserva de Emergência",
            "Viagem",
            "Carro Novo",
            "Entrada Apartamento",
            "Aposentadoria",
            "Educação dos Filhos",
        ]
        for _ in range(random.randint(1, 2)):
            target_amount = round(random.uniform(5000, 200000), 2)
            current_amount = round(random.uniform(0, target_amount), 2)
            status = random.choice(list(GoalStatus.choices))[0]
            target_date = timezone.now().date() + timezone.timedelta(days=random.randint(30, 3650))
            FinancialGoal.objects.create(
                user=user,
                name=random.choice(goal_names),
                target_amount=target_amount,
                current_amount=current_amount,
                target_date=target_date if status != GoalStatus.ACHIEVED else None,
                status=status,
            )

    def _create_net_worth_snapshots(self, user):
        for i in range(3):
            date = timezone.now().date() - timezone.timedelta(days=i * 30)
            assets = round(random.uniform(50000, 500000), 2)
            liabilities = round(random.uniform(10000, 100000), 2)
            NetWorthSnapshot.objects.create(
                user=user,
                date=date,
                assets=assets,
                liabilities=liabilities,
                net_worth=round(assets - liabilities, 2),
            )

    def _create_subscriptions(self, user, accounts):
        subscription_names = [
            "Netflix",
            "Spotify",
            "Amazon Prime",
            "Disney+",
            "iCloud+",
            "Google One",
        ]
        for _ in range(random.randint(2, 3)):
            account = random.choice(accounts) if accounts else None
            due_day = random.randint(1, 28)
            amount = round(random.uniform(9.9, 49.9), 2)
            subscription = Subscription.objects.create(
                user=user,
                connection=None,
                name=random.choice(subscription_names),
                category=random.choice(list(SubscriptionCategory.choices))[0],
                amount=amount,
                due_day=due_day,
                payment_account=account,
                is_active=random.choice([True, True, False]),
            )
            for _ in range(3):
                due_date = timezone.now().date() - timezone.timedelta(days=random.randint(0, 90))
                paid_date = due_date if random.random() > 0.3 else None
                status = SubscriptionStatus.PAID if paid_date else SubscriptionStatus.PENDING
                SubscriptionPayment.objects.create(
                    subscription=subscription,
                    due_date=due_date,
                    paid_date=paid_date,
                    status=status,
                    paid_amount=amount if paid_date else None,
                )

    def _create_categorization_rules(self, user):
        patterns = ["uber", "ifood", "99", "supermercado", "farmacia", "cinema"]
        categories = ["Transporte", "Alimentação", "Lazer", "Saúde"]
        for i in range(random.randint(2, 3)):
            CategorizationRule.objects.create(
                user=user,
                pattern=random.choice(patterns),
                category=random.choice(categories),
                priority=i,
                is_active=True,
            )

    def _create_document_chunks(self, user):
        for _ in range(random.randint(2, 3)):
            chunk = DocumentChunk.objects.create(
                user=user,
                source_type="extrato",
                source_id=fake.uuid4()[:12],
                content=fake.text(max_nb_chars=500),
                metadata={"bank": fake.company()},
                status=random.choice(list(DocumentChunkStatus.choices))[0],
                indexed_at=timezone.now() if random.random() > 0.5 else None,
            )
            Embedding.objects.create(
                chunk=chunk,
                vector=[random.random() for _ in range(10)],
                model="text-embedding-3-small",
            )
