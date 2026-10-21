"""Restaura a dimensao de `Embedding.vector` e recria o indice HNSW (cosseno).

Achado: no banco (Supabase e Neon) a coluna `finance_embedding.vector` esta como
`vector` sem dimensao, mas o model e a migration 0009 dizem `vector(768)`. O HNSW
exige dimensao fixa, entao o indice `embedding_vector_hnsw` nao podia existir.
Provavelmente a coluna foi alterada fora do historico de migrations e o indice
foi junto. Sem o indice, a busca por similaridade (`CosineDistance`) faz varredura
sequencial.

Passo 1 converte a coluna para `vector(768)` somente se ainda estiver sem dimensao.
O cast falha se alguma linha tiver dimensao diferente de 768, o que e o desejado.
Passo 2 cria o indice com os mesmos parametros do model.

Os campos ja estao no estado da migration, entao o `makemigrations` nao gera
nada; por isso o SQL e escrito a mao. `IF NOT EXISTS` e o `DO` deixam a migration
segura quando o estado ja esta correto.

Sem `CONCURRENTLY`: a tabela e pequena e a migration roda numa transacao. Se a
tabela crescer, reavaliar com `atomic = False` e `CREATE INDEX CONCURRENTLY`.
"""

from django.db import migrations

RESTORE_DIMENSION = """
DO $$
BEGIN
    IF (SELECT atttypmod FROM pg_attribute
        WHERE attrelid = 'finance_embedding'::regclass AND attname = 'vector') = -1 THEN
        ALTER TABLE finance_embedding ALTER COLUMN vector TYPE vector(768);
    END IF;
END $$;
"""


class Migration(migrations.Migration):
    dependencies = [("finance", "0028_transaction_category_suggestion")]

    operations = [
        migrations.RunSQL(
            sql=[
                RESTORE_DIMENSION,
                "CREATE INDEX IF NOT EXISTS embedding_vector_hnsw "
                "ON finance_embedding USING hnsw (vector vector_cosine_ops) "
                "WITH (m = 16, ef_construction = 64);",
            ],
            reverse_sql=[
                "DROP INDEX IF EXISTS embedding_vector_hnsw;",
                "ALTER TABLE finance_embedding ALTER COLUMN vector TYPE vector;",
            ],
        ),
    ]
