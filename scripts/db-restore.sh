set -e

DUMP="$1"
if [ -z "$DUMP" ]; then
  echo "Uso: mise run db-restore <arquivo.dump>"
  echo "Disponiveis:"
  ls -1t tmp/backups/*.dump 2>/dev/null | sed "s/^/  /" || echo "  (nenhum)"
  exit 1
fi
if [ ! -f "$DUMP" ]; then echo "Arquivo nao encontrado: $DUMP"; exit 1; fi

cd backend
# Carrega variaveis do .env
set -a; . ./.env; set +a
cd ..

echo "ATENCAO: isto SOBRESCREVE o banco \"$POSTGRES_DB\" com $DUMP"
printf "Digite RESTORE para confirmar: "
read CONFIRM
[ "$CONFIRM" = "RESTORE" ] || { echo "Abortado."; exit 1; }

# Restaura dump limpando objetos que existem e sem alterar ownership
docker exec -i -e PGPASSWORD="$POSTGRES_PASSWORD" myfinances-db-1 \
  pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists --no-owner < "$DUMP"
echo "Restaurado de $DUMP"
