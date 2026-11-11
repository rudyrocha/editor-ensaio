@echo off
setlocal EnableExtensions
set "DEST=D:\OFFline\Videos\@ensaio\_sistema\app"
set "LOGROOT=D:\OFFline\Videos\@ensaio\_sistema\logs"
set "SRC=%~dp0app"

echo Editor de Ensaios - atualizacao v3.2.1
echo Corrige janelas FFmpeg e retomada de analise interrompida.
echo.
if not exist "%SRC%\ensaio.py" goto :sem_fonte
if not exist "%SRC%\revisao_web.py" goto :sem_fonte
if not exist "%SRC%\interface.js" goto :sem_fonte
if not exist "%DEST%\ensaio.py" goto :sem_app

echo Feche o Editor antes de continuar.
choice /c SN /m "Confirma atualizacao com backup automatico"
if errorlevel 2 exit /b 1
if not exist "%LOGROOT%" mkdir "%LOGROOT%"
set "BACKUP=%LOGROOT%\backup_app_antes_v3_2_1_%RANDOM%"
mkdir "%BACKUP%" || goto :erro

for %%F in (ensaio.py revisao_web.py interface.js) do (
  copy /Y "%DEST%\%%F" "%BACKUP%\%%F" >nul || goto :erro
)
for %%F in (ensaio.py revisao_web.py interface.js) do (
  copy /Y "%SRC%\%%F" "%DEST%\%%F" >nul || goto :restaurar
)
echo.
echo Atualizacao concluida. Backup: %BACKUP%
echo Ambiente Python, brutas, revisoes, referencias e videos preservados.
echo Abra o Editor pelo atalho habitual. A versao mostrada deve ser 3.2.1.
pause
exit /b 0

:restaurar
echo ERRO ao copiar novos arquivos. Tentando restaurar backup...
for %%F in (ensaio.py revisao_web.py interface.js) do copy /Y "%BACKUP%\%%F" "%DEST%\%%F" >nul
:erro
echo A atualizacao nao foi concluida. Verifique: %BACKUP%
pause
exit /b 1
:sem_fonte
echo ERRO: extraia o ZIP inteiro; a pasta app deve ficar ao lado deste BAT.
pause
exit /b 1
:sem_app
echo ERRO: instalacao nao encontrada em %DEST%
pause
exit /b 1
