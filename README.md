RU

Этот репозиторий создан для развития редактора `SGMEditor`.

## Discord RPC

Редактор берёт настройки Discord RPC из отдельного файла:

`D:\Games\S.T.A.L.K.E.R\STSoC\LMR-Editor\discordrpc\config.json`

В этом файле задаются:

- `app_display_name`;
- `client_id`;
- `large_image_key`;
- `small_image_key`.

Пример:

```json
{
  "app_display_name": "SGMEditor",
  "client_id": "1494029959981830144",
  "large_image_key": "sgmeditor",
  "small_image_key": "sgmeditor_small"
}
```

Чтобы RPC работал, библиотека должна быть установлена:

```powershell
python -m pip install pypresence
```

Presence показывает:

- имя редактора из `app_display_name`;
- название проекта;
- название текущего редактируемого файла.

Важно: картинка появится только если в Discord Application загружены ассеты с ключами из `large_image_key` и `small_image_key`. Локальный файл [large_image.png](D:/Games/S.T.A.L.K.E.R/STSoC/LMR-Editor/discordrpc/large_image.png) сам по себе в RPC не отправляется, он нужен только как исходник для загрузки в Discord Developer Portal.

## EXE Build

One-file build files are prepared for this project:

- `build-exe.bat`
- `sg-editor.spec`
- `requirements-build.txt`

Build command:

```bat
build-exe.bat
```

The build embeds:

- `assets/`
- `discordrpc/`
- `editor_layout.json`
- `app_settings.json`

The resulting file is created at `dist\SGMEditor.exe`.
