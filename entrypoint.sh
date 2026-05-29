#!/bin/sh

su www-data -s /bin/sh -c "sh /opt/nginx/nginx.sh"
su nobody -s /bin/sh -c "sh run.sh run.metta $*"
