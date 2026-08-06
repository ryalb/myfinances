from django.db import migrations


def seed_institutions(apps, schema_editor):
    FinancialInstitution = apps.get_model("finance", "FinancialInstitution")
    institutions = [
        ("Banco do Brasil", "bb"),
        ("Bradesco", "bradesco"),
        ("Itaú Unibanco", "itau"),
        ("Santander", "santander"),
        ("Caixa Econômica Federal", "caixa"),
        ("Nubank", "nubank"),
        ("Inter", "inter"),
        ("BTG Pactual", "btg-pactual"),
        ("XP Investimentos", "xp-investimentos"),
        ("NuInvest", "nuinvest"),
        ("C6 Bank", "c6-bank"),
        ("PicPay", "picpay"),
        ("Neon", "neon"),
        ("Sofisa Direto", "sovisa-direto"),
        ("Daycoval", "daycoval"),
        ("Pan", "pan"),
        ("Votorantim", "votorantim"),
        ("Original", "original"),
        ("Safe", "safe"),
        ("RecargaPay", "recargapay"),
    ]
    created = 0
    for name, provider_id in institutions:
        obj, _ = FinancialInstitution.objects.update_or_create(
            provider_id=provider_id,
            defaults={"name": name},
        )
        created += int(_)
    print(f"Seeded {created} new financial institutions.")


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0002_transaction_provider_category"),
    ]

    operations = [
        migrations.RunPython(seed_institutions, migrations.RunPython.noop),
    ]
