@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_bench_windows.ps1"
if errorlevel 1 (
    echo.
    echo EXECUCAO ABORTADA. CONFIRME OUTPUT OFF NO PAINEL.
    exit /b 1
)
echo.
echo EXECUCAO CONCLUIDA. CONFIRME OUTPUT OFF NO PAINEL.
exit /b 0
