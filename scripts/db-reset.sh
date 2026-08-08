set -e

cd backend
# Carrega variaveis do .env
set -a; . ./.env; set +a
cd ..

echo "ATENCAO: isto APAGA o banco \"$POSTGRES_DB\" por completo (schema + dados)."
echo "Um backup sera feito antes, em tmp/backups/."
printf "Digite RESET para confirmar: "
read CONFIRM
[ "$CONFIRM" = "RESET" ] || { echo "Abortado."; exit 1; }

# Backup automatico antes de destruir o banco
mise run db-backup

echo "--- encerrando conexoes abertas com o banco ---"
# Termina backends ativos para permitir DROP DATABASE
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" myfinances-db-1 \
  psql -U "$POSTGRES_USER" -d postgres -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '"'"'$POSTGRES_DB'"'"' AND pid <> pg_backend_pid();" >/dev/null

echo "--- recriando o banco ---"
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" myfinances-db-1 \
  psql -U "$POSTGRES_USER" -d postgres -c "DROP DATABASE IF EXISTS $POSTGRES_DB;"
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" myfinances-db-1 \
  psql -U "$POSTGRES_USER" -d postgres -c "CREATE DATABASE $POSTGRES_DB OWNER $POSTGRES_USER;"

echo "--- rodando migrations do zero ---"
cd backend && uv run python manage.py migrate
