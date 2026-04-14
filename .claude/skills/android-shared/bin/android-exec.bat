@echo off
setlocal enabledelayedexpansion

if "%~1"=="" (
    echo Usage: android-exec.bat ^<script-name^> [args...]
    exit /b 1
)

REM 脚本位置 (必须在 shift 前获取)
set SCRIPT_DIR=%~dp0
set SCRIPT_NAME=%~1

REM 安全验证: 禁止路径遍历
echo %SCRIPT_NAME% | findstr /r "\.\." >nul
if %errorlevel% equ 0 (
    echo ERROR: Invalid script name (no .. allowed)
    exit /b 1
)

shift

REM 查找 Git Bash
set GIT_BASH=
if exist "D:\software\git\bin\bash.exe" set GIT_BASH=D:\software\git\bin\bash.exe
if exist "C:\Program Files\Git\bin\bash.exe" set GIT_BASH="C:\Program Files\Git\bin\bash.exe"
if exist "C:\Program Files (x86)\Git\bin\bash.exe" set GIT_BASH="C:\Program Files (x86)\Git\bin\bash.exe"

if not defined GIT_BASH (
    for /f "delims=" %%i in ('where git 2^>nul') do (
        set "GIT_PATH=%%~dpi"
        if exist "!GIT_PATH!..\bin\bash.exe" set "GIT_BASH=!GIT_PATH!..\bin\bash.exe"
    )
)

if not defined GIT_BASH (
    echo ERROR: Git Bash not found
    exit /b 1
)

set TARGET=%SCRIPT_DIR%%SCRIPT_NAME%

REM 验证目标脚本存在
if not exist "%TARGET%" (
    echo ERROR: Script not found: %TARGET%
    exit /b 1
)

%GIT_BASH% --login "%TARGET%" %*
