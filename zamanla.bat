@echo off
cd /d "%~dp0"
echo.
echo ============ OTOMATIK CALISTIRMA ============
echo  1) Kur (gunde 5 video uret ve paylas)
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
echo Saatleri SS:DD seklinde, aralarinda bosluk birakarak yaz.
echo Bos birakirsan onerilen saatler kullanilir.
set saatler=
set ig=
set /p saatler=Video saatleri [09:45 12:45 15:45 18:45 21:15]: 
if "%saatler%"=="" set saatler=09:45 12:45 15:45 18:45 21:15
set /p ig=Bunlardan hangileri Instagram'a da gitsin [12:45 18:45 21:15]: 
if "%ig%"=="" set ig=12:45 18:45 21:15

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0zamanla.ps1" -Saatler "%saatler%" -IgSaatler "%ig%"
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
