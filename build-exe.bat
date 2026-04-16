@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PYTHON_EXE="
call :find_python
if not defined PYTHON_EXE (
    echo Python was not found.
    echo Install Python 3.10+ and run this file again.
    exit /b 1
)

echo Using Python: %PYTHON_EXE%
echo.
echo Installing or updating build dependency...
"%PYTHON_EXE%" -m pip install --upgrade -r requirements-build.txt
if errorlevel 1 (
    echo Failed to install build dependencies.
    exit /b 1
)

echo.
echo Building one-file EXE with embedded assets...
"%PYTHON_EXE%" -m PyInstaller --noconfirm --clean "sg-editor.spec"
if errorlevel 1 (
    echo Build failed.
    exit /b 1
)

echo.
echo Build completed.
echo EXE path: %CD%\dist\SGMEditor.exe
exit /b 0

:find_python
for %%I in (py.exe python.exe) do (
    where %%I >nul 2>nul
    if not errorlevel 1 (
        for /f "delims=" %%P in ('where %%I 2^>nul') do (
            set "PYTHON_EXE=%%P"
            goto :eof
        )
    )
)

for %%P in (
    "C:\Python313\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
    "%LocalAppData%\Programs\Python\Python313\python.exe"
    "%LocalAppData%\Programs\Python\Python312\python.exe"
    "%LocalAppData%\Programs\Python\Python311\python.exe"
    "%LocalAppData%\Programs\Python\Python310\python.exe"
) do (
    if exist %%~P (
        set "PYTHON_EXE=%%~P"
        goto :eof
    )
)
goto :eof
