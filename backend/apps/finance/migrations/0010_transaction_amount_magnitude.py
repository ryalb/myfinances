"""Normaliza `Transaction.amount` para magnitude.

A Pluggy assina o valor e a convencao difere entre conta e cartao: em conta a saida
e negativa, em cartao a compra e positiva e o pagamento da fatura e negativo. O
`type` (DEBIT/CREDIT) e o indicador confiavel de direcao, entao o valor guardado
passa a ser sempre positivo.

Sem isto, as linhas gravadas antes da correcao continuam negativas e mantem os
sintomas: despesa somando negativo (taxa de poupanca acima de 100%), "--" na tela e
reconciliacao de assinatura que nunca casa.

SQL direto porque e um UPDATE em massa: trazer as linhas para o Python nao ajudaria.
Idempotente -- `ABS` de valor ja positivo nao muda nada, e o `WHERE` limita as linhas
tocadas. Sem reversao: o sinal original nao e recuperavel a partir da magnitude.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("finance", "0009_documentchunk_content_hash_alter_embedding_model_and_more")]

    operations = [
        migrations.RunSQL(
            sql="UPDATE finance_transaction SET amount = ABS(amount) WHERE amount < 0;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
