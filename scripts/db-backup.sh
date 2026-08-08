set -e

cd backend
# Carrega variaveis do .env (POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, etc.)
set -a; . ./.env; set +a
cd ..

mkdir -p tmp/backups
OUT="tmp/backups/myfinances-$(date +%Y%m%d-%H%M%S).dump"

# Dump em formato custom (restauravel via pg_restore)
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" myfinances-db-1 \
  pg_dump -Fc -U "$POSTGRES_USER" -d "$POSTGRES_DB" > "$OUT"

# Conta tabelas com dados para informar no resumo
TABLES=$(docker exec -i myfinances-db-1 pg_restore -l < "$OUT" 2>/dev/null | grep -c "TABLE DATA" || true)
echo "backup: $(pwd)/${OUT}"
echo "        $(du -h "$OUT" | cut -f1), ${TABLES} tabelas com dados"
