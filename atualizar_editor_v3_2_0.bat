@echo off
setlocal EnableExtensions
set "DEST=D:\OFFline\Videos\@ensaio\_sistema\app"
set "LOGROOT=D:\OFFline\Videos\@ensaio\_sistema\logs"
set "SRC=%~dp0app"

echo Atualizacao do Editor de Ensaios v3.2.0
echo.
if not exist "%SRC%\ensaio.py" (
  echo ERRO: a pasta app nao foi encontrada ao lado deste .bat.
  pause
  exit /b 1
)
if not exist "%DEST%\ensaio.py" (
  echo ERRO: instalacao existente nao encontrada em %DEST%
  pause
  exit /b 1
)

echo Feche o Editor de Ensaios antes de continuar.
choice /c SN /m "Confirma atualizacao e backup"
if errorlevel 2 exit /b 1
if not exist "%LOGROOT%" mkdir "%LOGROOT%"
set "BACKUP=%LOGROOT%\backup_app_antes_v3_2_0_%RANDOM%"
mkdir "%BACKUP%" || exit /b 1

echo Copiando backup para %BACKUP%
robocopy "%DEST%" "%BACKUP%" /E /XD .venv __pycache__ /R:1 /W:1 /NFL /NDL /NJH /NJS /NP
if errorlevel 8 goto :erro

echo Atualizando somente fontes e configuracao...
robocopy "%SRC%" "%DEST%" /E /XD .venv __pycache__ /R:1 /W:1 /NFL /NDL /NJH /NJS /NP
if errorlevel 8 goto :erro

echo.
echo Atualizacao concluida. Ambiente Python e dados preservados.
echo Pasta dos arquivos temporarios: processadas\AAAA-MM-DD\temporarios
echo Abra o Editor pelo atalho normal.
pause
exit /b 0

:erro
echo ERRO durante copia. Backup em: %BACKUP%
echo Os arquivos existentes nao foram removidos. Verifique antes de iniciar o editor.
pause
exit /b 1
