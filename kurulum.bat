@echo off
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python bulunamadi. python.org adresinden kur, kurarken "Add python.exe to PATH" kutusunu isaretle.
  pause
  exit /b 1
)
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
pip install -r requirements.txt
if not exist .env copy .env.example .env >nul
echo.
echo ============================================================
echo  Kurulum tamam.
echo  Simdi Not Defteri acilacak. GEMINI_API_KEY= satirinin sonuna
echo  anahtarini yapistir, kaydet (Ctrl+S) ve kapat.
echo ============================================================
pause
notepad .env
