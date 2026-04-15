@echo off
setlocal

set ROOT=D:\Games\S.T.A.L.K.E.R\STSoC\LMR-Editor
set EDITOR_EXE=%ROOT%\LMR Scenario Editor.exe
set RPC_DIR=%ROOT%\DiscordRPC Launcher
set RPC_SCRIPT=%RPC_DIR%\rpc_launcher.py

if not exist "%EDITOR_EXE%" (
  echo Editor not found: %EDITOR_EXE%
  pause
  exit /b 1
)

if not exist "%RPC_SCRIPT%" (
  echo RPC script not found: %RPC_SCRIPT%
  pause
  exit /b 1
)

cd /d "%RPC_DIR%"
python -c "import pypresence" >nul 2>&1
if errorlevel 1 (
  echo Installing pypresence...
  python -m pip install pypresence
)

start "LMR Editor" /D "%ROOT%" "%EDITOR_EXE%"
start "LMR RPC" python "%RPC_SCRIPT%"
