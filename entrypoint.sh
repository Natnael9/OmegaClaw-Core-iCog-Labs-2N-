#!/usr/bin/env bash
set -euo pipefail

cd /PeTTa

# 1. Start Nginx
su www-data -s /bin/sh -c "sh /opt/nginx/nginx.sh"

# 2. Setup Database Variables
export CHROMA_DB_PATH="${CHROMA_DB_PATH:-/PeTTa/chroma_db}"
IMPORT_KB_ON_START="${IMPORT_KB_ON_START:-1}"
IMPORT_KB_FORCE="${IMPORT_KB_FORCE:-0}"
EMBEDDING_PROVIDER="${embeddingprovider:-OpenAI}"
GATEWAY_URL="http://localhost:8080"

mkdir -p "${CHROMA_DB_PATH}"

normalize_provider() {
  echo "$1" | tr '[:upper:]' '[:lower:]'
}

# 3. Handle Knowledge Base Import
if [[ "${IMPORT_KB_ON_START}" == "1" ]]; then
  PROVIDER="$(normalize_provider "${EMBEDDING_PROVIDER}")"

  case "${PROVIDER}" in
    openai)
      if [[ -z "${OPENAI_API_KEY:-}" ]]; then
        echo "ERROR: OPENAI_API_KEY is required when EMBEDDING_PROVIDER=OpenAI." >&2
        exit 1
      fi

      SENTINEL="${CHROMA_DB_PATH}/.import-kb.openai.done"

      if [[ -f "${SENTINEL}" && "${IMPORT_KB_FORCE}" != "1" ]]; then
        echo "[entrypoint] import-kb already initialized with OpenAI embeddings; skipping."
      else
        echo "[entrypoint] Running import-kb with default OpenAI embeddings."
        echo "[entrypoint] CHROMA_DB_PATH=${CHROMA_DB_PATH}"
        import-knowledge
        date -Iseconds > "${SENTINEL}"
        echo "[entrypoint] import-kb complete."
      fi
      ;;

    local)
      SENTINEL="${CHROMA_DB_PATH}/.import-kb.local.done"

      if [[ -f "${SENTINEL}" && "${IMPORT_KB_FORCE}" != "1" ]]; then
        echo "[entrypoint] import-kb already initialized with local embeddings; skipping."
      else
        echo "[entrypoint] Running import-kb with default local embeddings."
        echo "[entrypoint] CHROMA_DB_PATH=${CHROMA_DB_PATH}"
        import-knowledge --local
        date -Iseconds > "${SENTINEL}"
        echo "[entrypoint] import-kb complete."
      fi
      ;;

    *)
      echo "ERROR: Unsupported EMBEDDING_PROVIDER='${EMBEDDING_PROVIDER}'." >&2
      echo "Use EMBEDDING_PROVIDER=OpenAI or EMBEDDING_PROVIDER=Local." >&2
      exit 1
      ;;
  esac

  # Ensure the runtime user 'nobody' has permissions to read/write the db
  chown -R nobody "${CHROMA_DB_PATH}" 2>/dev/null || true
fi

# 4. Scrub environment: only allowlisted vars survive.
SAFE_VARS="HOME USER PATH HOSTNAME TERM LANG LC_ALL \
  GATEWAY_URL PYTHONDONTWRITEBYTECODE PYTHONUNBUFFERED \
  HF_HOME SENTENCE_TRANSFORMERS_HOME HF_HUB_OFFLINE TRANSFORMERS_OFFLINE \
  OMEGACLAW_DIR MEMORY_DIR LLM_SERVER_LOCAL_URL TEST_SERVER_IP \
  CHROMA_DB_PATH OPENAI_API_KEY EMBEDDING_PROVIDER"

env_args=""
for var in $SAFE_VARS; do
  eval val=\${$var:-}
  if [ -n "$val" ]; then
    env_args="$env_args $var=$val"
  fi
done

# 5. Execute core application
exec env -i $env_args su nobody -s /bin/sh -c "sh run.sh run.metta $*"