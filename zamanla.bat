@echo off
cd /d "%~dp0"
echo.
echo ============ OTOMATIK CALISTIRMA ============
echo  1) Kur (gunde 3 kere uret ve paylas)
echo  2) Kaldir
echo  3) Uyandirma testi (X dakika sonra bir kere, PAYLASMAZ)
echo =============================================
set /p z=Secimin (1-3): 
if "%z%"=="3" goto test
if "%z%"=="2" (
  powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0zamanla.ps1" -Kaldir
  pause
  exit /b 0
)
if not "%z%"=="1" exit /b 0

echo.
echo Saatleri SS:DD seklinde yaz. Bos birakirsan parantezdeki kullanilir.
set /p s1=1. saat (12:00): 
set /p s2=2. saat (17:00): 
set /p s3=3. saat (21:00): 
if "%s1%"=="" set s1=12:00
if "%s2%"=="" set s2=17:00
if "%s3%"=="" set s3=21:00

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0zamanla.ps1" -S1 %s1% -S2 %s2% -S3 %s3%
echo.
echo ONEMLI: Bilgisayari KAPATMA, uyku moduna al. Uyandiginda sifre sormamasi gerekiyor
echo (Ayarlar - Hesaplar - Oturum acma secenekleri - "Uzaktaysaniz..." = Hicbir zaman).
echo Calisma kayitlari: kayit.txt
pause
exit /b 0

:test
set dk=
set /p dk=Kac dakika sonra? [5]: 
if "%dk%"=="" set dk=5
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0zamanla.ps1" -Test %dk%
echo.
echo Simdi bilgisayari UYKU moduna al (Baslat - Guc - Uyku).
echo %dk% dakika sonra kendi uyanip bir test videosu uretecek (paylasmaz).
echo Sonra kayit.txt dosyasinin en altina ve cikti\spoderman klasorune bak.
pause
exit /b 0
