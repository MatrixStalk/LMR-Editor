@echo off
setlocal
cd /d "D:\Games\S.T.A.L.K.E.R\STSoC\LMR-Editor\DiscordRPC Launcher"
echo [%date% %time%] run_rpc.bat started>>"rpc-run.log"
taskkill /IM "LmrDiscordRpc.exe" /F >nul 2>&1
if exist "LmrDiscordRpc.exe" (
  "LmrDiscordRpc.exe" >> "rpc-run.log" 2>&1
) else (
  where python >nul 2>&1
  if %errorlevel%==0 (
    python "rpc_launcher.py" >> "rpc-run.log" 2>&1
  ) else (
    py -3 "rpc_launcher.py" >> "rpc-run.log" 2>&1
  )
)
