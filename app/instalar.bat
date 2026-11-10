@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo Editor de Ensaios - instalacao do ambiente local
echo.

where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo ERRO: FFmpeg nao foi encontrado no PATH.
  pause
  exit /b 1
)
where ffprobe >nul 2>nul
if errorlevel 1 (
  echo ERRO: ffprobe nao foi encontrado no PATH.
  pause
  exit /b 1
)

set "PY_CMD="
where py >nul 2>nul
if not errorlevel 1 (
  py -3.13 -c "import sys" >nul 2>nul && set "PY_CMD=py -3.13"
  if not defined PY_CMD py -3.14 -c "import sys" >nul 2>nul && set "PY_CMD=py -3.14"
  if not defined PY_CMD py -3.12 -c "import sys" >nul 2>nul && set "PY_CMD=py -3.12"
  if not defined PY_CMD py -3.11 -c "import sys" >nul 2>nul && set "PY_CMD=py -3.11"
  if not defined PY_CMD py -3.10 -c "import sys" >nul 2>nul && set "PY_CMD=py -3.10"
)
if not defined PY_CMD (
  where python >nul 2>nul
  if not errorlevel 1 set "PY_CMD=python"
)
if not defined PY_CMD (
  echo ERRO: Python 3.10 a 3.14 nao foi encontrado.
  pause
  exit /b 1
)

echo Python selecionado:
%PY_CMD% --version

if not exist ".venv\Scripts\python.exe" (
  echo Criando ambiente virtual isolado do Editor de Ensaios...
  %PY_CMD% -m venv .venv
  if errorlevel 1 goto :erro
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
if errorlevel 1 goto :erro
python -m pip install -r requirements.txt
if errorlevel 1 goto :erro

echo Verificando dependencias...
python -c "import numpy, soundfile, cffi; print('NumPy', numpy.__version__); print('SoundFile', soundfile.__version__); print('CFFI', cffi.__version__)"
if errorlevel 1 goto :erro

echo.
echo Instalacao concluida.
exit /b 0

:erro
echo.
echo A instalacao falhou. Consulte as mensagens acima.
pause
exit /b 1
