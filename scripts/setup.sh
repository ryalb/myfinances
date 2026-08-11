set -e

cd backend
# Sobe Postgres/Redis (e outros servicos do compose) via Podman
podman compose up -d --force-recreate --remove-orphans
uv sync --group dev

cd ..

cd frontend
bun install

cd ..

# Instala o Ollama via Homebrew caso ainda nao esteja disponivel no PATH
if ! command -v ollama >/dev/null 2>&1; then
  echo "--- instalando ollama via homebrew ---"
  brew install ollama
fi

# brew services start e idempotente: nao reinicia o servico se ja estiver rodando
echo "--- garantindo que o servico ollama esta rodando ---"
brew services start ollama

# Espera o servidor aceitar conexoes antes de tentar puxar os modelos
until ollama list >/dev/null 2>&1; do sleep 1; done

# So baixa cada modelo se ainda nao estiver na maquina, evitando checagem
# de manifesto remoto (e trafego de rede) a cada `mise run setup`
pull_model_if_missing() {
  model="$1"
  # `ollama list` sempre mostra a tag (ex: "nomic-embed-text:latest"), entao
  # modelos pedidos sem tag precisam do sufixo ":latest" para a comparacao bater
  case "$model" in
    *:*) tagged_model="$model" ;;
    *) tagged_model="$model:latest" ;;
  esac

  if ollama list | awk '{print $1}' | grep -qx "$tagged_model"; then
    echo "--- modelo $model ja esta instalado ---"
  else
    echo "--- baixando modelo $model ---"
    ollama pull "$model"
  fi
}

pull_model_if_missing "qwen2.5:14b"
pull_model_if_missing "nomic-embed-text"
