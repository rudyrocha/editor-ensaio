@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Ambiente virtual nao encontrado. Execute instalar.bat primeiro.
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
python revisao_web.py
set RC=%ERRORLEVEL%
echo.
if not "%RC%"=="0" echo A interface terminou com erro %RC%.
pause
exit /b %RC%
