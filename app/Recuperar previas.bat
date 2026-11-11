@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
title Editor de Ensaios - Recuperar previas
if not exist ".venv\Scripts\python.exe" (
 echo ERRO: Python do Editor nao encontrado. Coloque os dois arquivos na pasta _sistema\app.
 pause
 exit /b 1
)
echo =====================================================
echo RECUPERACAO DE PREVIAS - SEM REANALISAR O ENSAIO
echo =====================================================
echo Feche o Editor e as abas do navegador antes de continuar.
echo Nao altera segmentos.csv, manifesto.json, identificacoes ou referencias.
echo.
choice /c SN /m "Editor fechado e backup feito. Continuar"
if errorlevel 2 exit /b 1
".venv\Scripts\python.exe" "%~dp0recuperar_previas.py"
set "RESULT=%ERRORLEVEL%"
echo.
if not "%RESULT%"=="0" echo A RECUPERACAO NAO FOI CONCLUIDA. Guarde o erro para diagnostico.
pause
exit /b %RESULT%