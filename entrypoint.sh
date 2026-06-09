#!/bin/sh
set -eu

su www-data -s /bin/sh -c "sh /opt/nginx/nginx.sh"

GATEWAY_URL=http://localhost:8080

# Scrub environment: only allowlisted, non-secret vars survive.
SAFE_VARS="HOME USER PATH HOSTNAME TERM LANG LC_ALL \
  GATEWAY_URL PYTHONDONTWRITEBYTECODE PYTHONUNBUFFERED \
  HF_HOME SENTENCE_TRANSFORMERS_HOME HF_HUB_OFFLINE TRANSFORMERS_OFFLINE \
  OMEGACLAW_DIR MEMORY_DIR LLM_SERVER_LOCAL_URL GATEWAY_URL TEST_SERVER_IP"

env_args=""
for var in $SAFE_VARS; do
  eval val=\${$var:-}
  if [ -n "$val" ]; then
    env_args="$env_args $var=$val"
  fi
done

exec env -i $env_args su nobody -s /bin/sh -c "sh run.sh run.metta $*"
