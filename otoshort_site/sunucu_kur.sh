#!/bin/bash
# Zaply sunucu kurulumu (Ubuntu/Debian VPS). Bu klasörün içinden çalıştır:  bash sunucu_kur.sh
# İlk çalıştırmada .env'yi soru sorarak oluşturur, sonra siteyi Docker ile https'li olarak başlatır.
# Tekrar çalıştırmak güvenlidir: mevcut .env ve veriler (saas_veri/) korunur, sadece site güncellenip yeniden başlar.
set -e
cd "$(dirname "$0")"

if ! command -v docker >/dev/null 2>&1; then
  read -r -p "Docker kurulu değil. Şimdi kurulsun mu? (e/h) " a
  [ "$a" = "e" ] || { echo "Docker olmadan kurulum yapılamaz."; exit 1; }
  curl -fsSL https://get.docker.com | sh
fi

if [ ! -f .env ]; then
  echo "== İlk kurulum: birkaç soru =="
  read -r -p "Alan adı (ör. zaply.app, başında https olmadan): " DOMAIN
  read -r -p "Yönetici e-postan (havaleleri onaylayacak hesap): " ADMIN
  read -r -p "Google AI Studio API anahtarı (şimdi yoksa boş bırak): " GKEY
  SECRET=$(python3 -c "import secrets;print(secrets.token_urlsafe(48))" 2>/dev/null || head -c 48 /dev/urandom | base64 | tr -d '/+=\n')
  cp .env.ornek .env
  set_env() { if grep -q "^$1=" .env; then sed -i "s|^$1=.*|$1=$2|" .env; else echo "$1=$2" >> .env; fi; }
  set_env GIZLI_ANAHTAR "$SECRET"
  set_env ALAN_ADI "$DOMAIN"
  set_env SITE_ADRESI "https://$DOMAIN"
  set_env ADMIN_EPOSTALAR "$ADMIN"
  set_env GEMINI_API_KEY "$GKEY"
  set_env SAHTE_AI 0
  set_env VERI_KLASORU /veri
  chmod 600 .env
  echo
  echo ".env oluşturuldu. Kalan ayarları (SMTP, IBAN, şirket bilgileri) şu komutla doldur:  nano .env"
  echo "Alan adının DNS'inde A kaydı bu sunucunun IP'sini göstermeli: $(curl -fsS -4 ifconfig.me 2>/dev/null || echo '?')"
  echo
fi

mkdir -p saas_veri
docker compose up -d --build
echo
echo "Site başlatıldı. Birkaç dakika içinde https sertifikası alınır."
echo "Durum:        docker compose ps"
echo "Günlükler:    docker compose logs -f site"
echo "Eksik ayarlar:"
sleep 5
docker compose exec -T site python -m saas.hazirlik || true
