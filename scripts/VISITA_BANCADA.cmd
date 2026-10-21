@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0visita_bancada_windows.ps1" %*
if errorlevel 1 (
    echo.
    echo VISITA PARADA. CONFIRME OUTPUT OFF NO PAINEL. Para retomar, rode este comando de novo.
    pause
    exit /b 1
)
echo.
echo VISITA ENCERRADA. CONFIRME OUTPUT OFF NO PAINEL.
pause
exit /b 0
