@echo off
setlocal EnableExtensions

rem Este arquivo deve ficar junto ao Editor de Ensaios.vbs em _sistema\app.
set "EDITOR_APP=%~dp0"
set "EDITOR_TARGET=%EDITOR_APP%Editor de Ensaios.vbs"
set "EDITOR_ICON=D:\OFFline\Videos\@ensaio\_sistema\assets\Editor_Diogenes.ico"

if not exist "%EDITOR_TARGET%" (
    echo ERRO: o lancador do Editor nao foi encontrado:
    echo "%EDITOR_TARGET%"
    echo Coloque este BAT em D:\OFFline\Videos\@ensaio\_sistema\app.
    pause
    exit /b 2
)

if not exist "%EDITOR_ICON%" (
    echo ERRO: o icone nao foi encontrado:
    echo "%EDITOR_ICON%"
    echo Salve o arquivo Editor_Diogenes.ico na pasta _sistema\assets.
    echo O atalho existente nao foi alterado.
    pause
    exit /b 2
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='Stop'; try { $desktop=[Environment]::GetFolderPath('DesktopDirectory'); if (-not $desktop) { throw 'Area de Trabalho nao localizada' }; $link=Join-Path $desktop 'Editor de Ensaios.lnk'; $shell=New-Object -ComObject WScript.Shell; $shortcut=$shell.CreateShortcut($link); $shortcut.TargetPath=$env:EDITOR_TARGET; $shortcut.WorkingDirectory=$env:EDITOR_APP; $shortcut.IconLocation=$env:EDITOR_ICON + ',0'; $shortcut.Description='Editor de Ensaios - Banda Diogenes'; $shortcut.Save(); Write-Host ('Atalho criado ou atualizado: ' + $link); Write-Host ('Icone: ' + $env:EDITOR_ICON) } catch { Write-Error $_; exit 1 }"

if errorlevel 1 (
    echo ERRO: nao foi possivel atualizar o atalho.
    pause
    exit /b 1
)

echo.
echo Atalho configurado. O aplicativo e os dados nao foram modificados.
echo Se o icone antigo permanecer visivel, atualize a Area de Trabalho com F5.
pause
exit /b 0
