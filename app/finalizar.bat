@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Ambiente virtual nao encontrado. Execute instalar.bat primeiro.
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
echo Este comando e uma alternativa de emergencia a interface web.
echo Ele usa os ultimos dados salvos pela pagina de revisao.
python ensaio.py finalizar
set RC=%ERRORLEVEL%
echo.
if not "%RC%"=="0" echo A finalizacao terminou com erro %RC%.
pause
exit /b %RC%
