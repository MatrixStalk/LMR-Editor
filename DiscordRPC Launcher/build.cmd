@echo off
setlocal

set CSC=C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe
if not exist "%CSC%" set CSC=C:\Windows\Microsoft.NET\Framework\v4.0.30319\csc.exe

if not exist "%CSC%" (
  echo csc.exe not found.
  exit /b 1
)

if not exist "libs\lib\net45\DiscordRPC.dll" (
  echo Missing libs\lib\net45\DiscordRPC.dll
  exit /b 1
)

if not exist "libs\lib\net45\Newtonsoft.Json.dll" (
  echo Missing libs\lib\net45\Newtonsoft.Json.dll
  exit /b 1
)

"%CSC%" /nologo /target:exe /out:DiscordRpcLauncher.exe /platform:anycpu /optimize+ /reference:libs\lib\net45\DiscordRPC.dll /reference:libs\lib\net45\Newtonsoft.Json.dll DiscordRpcLauncher.cs
if errorlevel 1 exit /b 1

copy /Y "libs\lib\net45\DiscordRPC.dll" "." >nul
copy /Y "libs\lib\net45\Newtonsoft.Json.dll" "." >nul

echo Build complete: DiscordRpcLauncher.exe
