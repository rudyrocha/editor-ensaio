@echo off
setlocal EnableExtensions
set "SRC=%~dp0app"
set "ROOT=D:\OFFline\Videos\@ensaio"
set "DEST=%ROOT%\_sistema\app"
set "LOG=%ROOT%\_sistema\logs"

echo ============================================================
echo Editor de Ensaios v3.3.0 - atualizacao incremental
echo ============================================================
echo Feche o editor pelo botao Encerrar e feche TODAS as abas dele.
echo.
if not exist "%SRC%\ensaio.py" goto error_source
if not exist "%SRC%\revisao_web.py" goto error_source
if not exist "%SRC%\interface.js" goto error_source
if not exist "%SRC%\interface.css" goto error_source
if not exist "%DEST%\ensaio.py" goto error_dest
if not exist "%LOG%" mkdir "%LOG%"
choice /c SN /m "Editor fechado? Confirma backup e atualizacao"
if errorlevel 2 exit /b 1
set "BACKUP=%LOG%\backup_app_antes_3_3_0_%RANDOM%_%RANDOM%"
mkdir "%BACKUP%" || goto error_backup
for %%F in (ensaio.py revisao_web.py interface.js interface.css) do (
  copy /Y "%DEST%\%%F" "%BACKUP%\%%F" >nul || goto error_backup
)
for %%F in (ensaio.py revisao_web.py interface.js interface.css) do (
  copy /Y "%SRC%\%%F" "%DEST%\%%F" >nul || goto rollback
)
echo.
echo Atualizacao concluida.
echo Backup do codigo: "%BACKUP%"
echo Agora abra o Editor e confira que a pagina mostra versao 3.3.0.
echo Pastas de audio, referencias e ambiente Python nao foram alterados.
pause
exit /b 0
:rollback
echo ERRO durante copia. Tentando restaurar os arquivos anteriores...
for %%F in (ensaio.py revisao_web.py interface.js interface.css) do (
  if exist "%BACKUP%\%%F" copy /Y "%BACKUP%\%%F" "%DEST%\%%F" >nul
)
echo Confira o backup em "%BACKUP%".
pause
exit /b 2
:error_source
echo ERRO: extraia TODO o ZIP da raiz do repositorio, incluindo a pasta app.
pause
exit /b 2
:error_dest
echo ERRO: nao encontrei a instalacao em "%DEST%".
pause
exit /b 2
:error_backup
echo ERRO: nao foi possivel criar backup. Nenhum arquivo novo aplicado.
pause
exit /b 2