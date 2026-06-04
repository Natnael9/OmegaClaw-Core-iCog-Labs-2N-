#!/usr/bin/env bash
set -euo pipefail

cd /PeTTa

export CHROMA_DB_PATH="${CHROMA_DB_PATH:-/PeTTa/chroma_db}"

IMPORT_KB_ON_START="${IMPORT_KB_ON_START:-1}"
IMPORT_KB_FORCE="${IMPORT_KB_FORCE:-0}"

# OpenAI | Local
EMBEDDING_PROVIDER="${embeddingprovider:-OpenAI}"

mkdir -p "${CHROMA_DB_PATH}"

normalize_provider() {
  echo "$1" | tr '[:upper:]' '[:lower:]'
}

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
fi

exec sh run.sh run.metta "$@"