#!/bin/sh
set -eu

# TODO: at the moment MM_URL is a command line parameter not an environment
# variable. This means when user sets this parameter we don't have its value
# here. On the other hand user cannot set it via scripts/omegaclaw and when
# user runs OmegaClaw from the command line this proxy is not started
# automatically. At some point this parameter should be parsed in the
# entrypoint as well.
export MM_UPSTREAM_URL=${MM_URL:-https://chat.singularitynet.io}
SUBST_VARS=$(grep -o '\${[A-Z_0-9]*}' /opt/nginx/nginx.conf.template | sort -u | tr '\n' ' ')
NGINX_CONFIG=/opt/nginx/nginx.conf
touch "${NGINX_CONFIG}"
chmod 0600 "${NGINX_CONFIG}"
envsubst "$SUBST_VARS" \
    < /opt/nginx/nginx.conf.template \
    > "${NGINX_CONFIG}"

nginx -c "${NGINX_CONFIG}"

