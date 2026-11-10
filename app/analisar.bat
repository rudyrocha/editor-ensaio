@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Ambiente virtual nao encontrado. Execute instalar.bat primeiro.
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
python ensaio.py analisar
set RC=%ERRORLEVEL%
if not "%RC%"=="0" goto :erro

echo.
echo Abrindo a interface de revisao no navegador...
python revisao_web.py
set RC=%ERRORLEVEL%
if not "%RC%"=="0" goto :erro

echo.
echo Interface encerrada.
pause
exit /b 0

:erro
echo.
echo O processo terminou com erro %RC%.
pause
exit /b %RC%
