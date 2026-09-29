@echo off
cd /d "%~dp0"
echo.
echo ============ OTOMATIK CALISTIRMA ============
echo  1) Kur (gunde 3 kere uret ve paylas)
echo  2) Kaldir
echo =============================================
set /p z=Secimin (1-2): 
if "%z%"=="2" goto kaldir
if not "%z%"=="1" exit /b 0

echo.
echo Saatleri SS:DD seklinde yaz. Bos birakirsan parantezdeki kullanilir.
set /p s1=1. saat (12:00): 
set /p s2=2. saat (17:00): 
set /p s3=3. saat (21:00): 
if "%s1%"=="" set s1=12:00
if "%s2%"=="" set s2=17:00
if "%s3%"=="" set s3=21:00

schtasks /Create /TN "Shitpost 1" /TR "\"%~dp0calistir.bat\"" /SC DAILY /ST %s1% /F
schtasks /Create /TN "Shitpost 2" /TR "\"%~dp0calistir.bat\"" /SC DAILY /ST %s2% /F
schtasks /Create /TN "Shitpost 3" /TR "\"%~dp0calistir.bat\"" /SC DAILY /ST %s3% /F
echo.
echo Kuruldu: her gun %s1%, %s2% ve %s3%.
echo O saatlerde bilgisayar ACIK ve KILITSIZ olmali (program Chrome'u acip klavyeyle gonderiyor).
echo Calisma kayitlari: kayit.txt
pause
exit /b 0

:kaldir
schtasks /Delete /TN "Shitpost 1" /F
schtasks /Delete /TN "Shitpost 2" /F
schtasks /Delete /TN "Shitpost 3" /F
echo Otomatik calistirma kaldirildi.
pause
exit /b 0
