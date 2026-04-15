@echo off
setlocal
chcp 65001 >nul

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
  py -3 -m pip install pypresence
)

start "LMR Editor" /D "%ROOT%" "%EDITOR_EXE%"
start "LMR RPC" "%RPC_DIR%\run_rpc.bat"
