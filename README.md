RU

Этот репозиторий создан для развития редактора `Soviet Games Editor`.

## Discord RPC

Редактор обновляет Discord Rich Presence в таком формате:

- название приложения в Discord: `Soviet Games Editor`;
- строка проекта: имя открытого проекта;
- строка файла: имя текущего редактируемого файла.

Чтобы RPC заработал, установите библиотеку:

```powershell
python -m pip install pypresence
```

Перед запуском задайте `DISCORD_RPC_CLIENT_ID` для вашего Discord application:

```powershell
$env:DISCORD_RPC_CLIENT_ID="YOUR_DISCORD_APP_ID"
python .\sg-editor.py
```

Если `pypresence` не установлен или переменная `DISCORD_RPC_CLIENT_ID` не задана, редактор продолжит работать без Discord RPC.
