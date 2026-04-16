@echo off
cd /d "%~dp0"
echo Running syntax check...
python -m py_compile "sg-editor.py"
if errorlevel 1 (
    echo.
    echo Syntax check failed.
    pause
    exit /b 1
)

echo.
echo Running import smoke test...
echo import importlib.util; spec = importlib.util.spec_from_file_location("sg_editor", "sg-editor.py"); module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); print("ok") | python -
if errorlevel 1 (
    echo.
    echo Smoke test failed.
    pause
    exit /b 1
)

echo.
echo All checks passed.
pause
