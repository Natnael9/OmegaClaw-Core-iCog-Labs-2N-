#!/bin/sh
set -eu

export MM_UPSTREAM_URL=${MM_URL:-https://chat.singularitynet.io}
SUBST_VARS=$(grep -o '\${[A-Z_0-9]*}' /opt/nginx/nginx.conf.template | sort -u | tr '\n' ' ')
envsubst "$SUBST_VARS" \
    < /opt/nginx/nginx.conf.template \
    > /opt/nginx/nginx.conf

nginx -c /opt/nginx/nginx.conf

