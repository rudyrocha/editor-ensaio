@echo off
setlocal
cd /d "%~dp0"
set "TARGET=%~dp0Editor de Ensaios.vbs"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$desktop=[Environment]::GetFolderPath('Desktop'); $shortcut=Join-Path $desktop 'Editor de Ensaios.lnk'; $w=New-Object -ComObject WScript.Shell; $s=$w.CreateShortcut($shortcut); $s.TargetPath='%TARGET%'; $s.WorkingDirectory='%~dp0'; $s.Description='Editor local de ensaios da banda - v3.1'; $s.Save(); Write-Host $shortcut"
if errorlevel 1 (
  echo Nao foi possivel criar o atalho automaticamente.
  pause
  exit /b 1
)
echo.
echo Atalho criado na Area de Trabalho: Editor de Ensaios
pause
