@echo off
setlocal EnableExtensions
set "SRC=%~dp0app"
set "ROOT=D:\OFFline\Videos\@ensaio"
set "DEST=%ROOT%\_sistema\app"
set "LOG=%ROOT%\_sistema\logs"
set "CHECK=%~dp0verificar_editor_fechado.ps1"

echo ============================================================
echo Editor de Ensaios - atualizacao 3.3.1
echo ============================================================
echo Feche o Editor pelo botao Encerrar antes de atualizar.
echo Fechar so a aba do navegador nao encerra o servidor.
echo.
if not exist "%CHECK%" goto error_source
if not exist "%SRC%\ensaio.py" goto error_source
if not exist "%SRC%\revisao_web.py" goto error_source
if not exist "%DEST%\ensaio.py" goto error_dest
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%CHECK%" -ScriptPath "%DEST%\revisao_web.py"
if errorlevel 1 goto error_running
choice /c SN /m "Confirma backup e atualizacao"
if errorlevel 2 exit /b 1
if not exist "%LOG%" mkdir "%LOG%"
set "BACKUP=%LOG%\backup_app_antes_3_3_1_%RANDOM%_%RANDOM%"
mkdir "%BACKUP%" || goto error_backup
copy /Y "%DEST%\ensaio.py" "%BACKUP%\ensaio.py" >nul || goto error_backup
copy /Y "%DEST%\revisao_web.py" "%BACKUP%\revisao_web.py" >nul || goto error_backup
copy /Y "%SRC%\ensaio.py" "%DEST%\ensaio.py" >nul || goto rollback
copy /Y "%SRC%\revisao_web.py" "%DEST%\revisao_web.py" >nul || goto rollback
echo.
echo Atualizacao 3.3.1 concluida.
echo Backup: "%BACKUP%"
echo Nenhum WAV, referencia, revisao ou biblioteca Python foi alterado.
pause
exit /b 0
:rollback
echo ERRO: restaurando versao anterior...
copy /Y "%BACKUP%\ensaio.py" "%DEST%\ensaio.py" >nul
copy /Y "%BACKUP%\revisao_web.py" "%DEST%\revisao_web.py" >nul
pause
exit /b 2
:error_running
echo Atualizacao cancelada. Encerre os processos indicados acima.
pause
exit /b 3
:error_source
echo ERRO: extraia o ZIP inteiro, incluindo app e verificar_editor_fechado.ps1.
pause
exit /b 2
:error_dest
echo ERRO: instalacao nao encontrada em "%DEST%".
pause
exit /b 2
:error_backup
echo ERRO: falha ao criar backup; nenhuma versao nova deve ser instalada.
pause
exit /b 2
