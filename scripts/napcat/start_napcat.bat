@echo off
rem ============================================================
rem  Start NapCat (OneKey style) and inject into QQNT.
rem  IMPORTANT: this file must stay ASCII-only. cmd.exe reads
rem  batch files with the ANSI codepage; Chinese comments get
rem  mangled and can break IF blocks / SET commands.
rem
rem  Edit the paths below for your machine.
rem ============================================================

set "QQ_DIR=C:\Program Files\Tencent\QQNT"
set "QQ_EXE=%QQ_DIR%\QQ.exe"
set "NAPCAT_DIR=%~dp0"
if "%NAPCAT_DIR:~-1%"=="\" set "NAPCAT_DIR=%NAPCAT_DIR:~0,-1%"

rem --- Single instance guard -------------------------------------
rem If QQ is already running, NapCat cannot inject into it.
rem Starting another instance causes a double-login that kicks the
rem previous session offline (and invalidates quick-login tickets).
tasklist /FI "IMAGENAME eq QQ.exe" | find /I "QQ.exe" >nul
if not errorlevel 1 (
    echo [start_napcat] QQ.exe already running, skip.
    exit /b 0
)

rem --- NapCat environment ----------------------------------------
set "NAPCAT_PATCH_PACKAGE=%NAPCAT_DIR%\qqnt.json"
set "NAPCAT_LOAD_PATH=%NAPCAT_DIR%\loadNapCat.js"
set "NAPCAT_INJECT_PATH=%NAPCAT_DIR%\NapCatWinBootHook.dll"
set "NAPCAT_LAUNCHER_PATH=%NAPCAT_DIR%\NapCatWinBootMain.exe"
set "NAPCAT_MAIN_PATH=%NAPCAT_DIR%\napcat.mjs"

cd /d "%NAPCAT_DIR%"
echo [start_napcat] starting QQ + NapCat from %NAPCAT_DIR%
start "" "%NAPCAT_DIR%\NapCatWinBootMain.exe" "%QQ_EXE%" "%NAPCAT_DIR%\NapCatWinBootHook.dll"
