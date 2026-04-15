# Discord RPC for LMR Scenario Editor

## Что сделано
- `DiscordRpcLauncher.exe` (собирается из `DiscordRpcLauncher.cs`) следит за процессом `LMR Scenario Editor`.
- Пока редактор запущен, в Discord показывается Rich Presence.
- Когда редактор закрыт, Presence очищается.

## Быстрый старт
1. Открой `discord-rpc-config.json`.
2. Укажи `DiscordApplicationId` (ID твоего Discord Application).
3. В Discord Developer Portal добавь Art Asset с key `app` (или поменяй `LargeImageKey` в конфиге).
4. Запусти `build.cmd`.
5. Запусти `DiscordRpcLauncher.exe`.

## Примечания
- `AutoLaunchEditor=true` автоматически запускает `LMR Scenario Editor.exe`.
- `AutoExitWhenEditorClosed=true` закрывает лаунчер после закрытия редактора.
- Discord-клиент должен быть запущен.
