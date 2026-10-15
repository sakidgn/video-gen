#!/bin/sh
# Veri klasörü (sunucudaki ./saas_veri) root'a aitse sahipliği 'app' kullanıcısına verir,
# sonra siteyi yetkisiz 'app' kullanıcısıyla başlatır.
set -e
if [ "$(id -u)" = "0" ]; then
  [ "$(stat -c %u /veri)" = "1000" ] || chown -R app:app /veri
  exec setpriv --reuid=app --regid=app --init-groups "$@"
fi
exec "$@"
