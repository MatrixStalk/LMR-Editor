import csv
import io
import json
import os
import subprocess
import sys
import time
from datetime import datetime

from pypresence import Presence

CONFIG_NAME = "discord-rpc-config.json"
LOG_NAME = "rpc-python.log"


def log(msg: str):
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {msg}"
    try:
        print(line, flush=True)
    except Exception:
        pass
    try:
        with open(LOG_NAME, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_config():
    with open(CONFIG_NAME, "r", encoding="utf-8") as f:
        return json.load(f)


def decode_tasklist_output(raw: bytes) -> str:
    for enc in ("utf-8", "cp866", "cp1251", "mbcs"):
        try:
            txt = raw.decode(enc)
            if "Image Name" in txt or "Имя образа" in txt:
                return txt
        except Exception:
            continue
    return raw.decode("utf-8", errors="ignore")


def _text_score(s: str) -> int:
    cyr = sum(1 for ch in s if "А" <= ch <= "я" or ch in "Ёё")
    bad = sum(1 for ch in s if ch in "ÐÑÂÃ�")
    return cyr * 3 - bad


def repair_mojibake(text: str) -> str:
    candidates = [text]
    transforms = [
        ("latin1", "utf-8"),
        ("cp1251", "utf-8"),
        ("cp1252", "utf-8"),
        ("cp866", "utf-8"),
        ("latin1", "cp1251"),
        ("cp1252", "cp1251"),
        ("cp866", "cp1251"),
        ("cp1251", "cp866"),
    ]
    for src, dst in transforms:
        try:
            candidates.append(text.encode(src).decode(dst))
        except Exception:
            pass
    return max(candidates, key=_text_score)


def get_tasklist_rows(process_name: str, verbose: bool):
    args = ["tasklist", "/FI", f"IMAGENAME eq {process_name}.exe", "/FO", "CSV"]
    if verbose:
        args.insert(1, "/V")
    try:
        raw = subprocess.check_output(args, creationflags=0x08000000)
        out = decode_tasklist_output(raw)
        reader = csv.reader(io.StringIO(out))
        rows = list(reader)
        if len(rows) <= 1:
            return []
        data_rows = rows[1:]
        result = []
        for row in data_rows:
            if not row:
                continue
            image_name = (row[0] if len(row) > 0 else "").strip().lower()
            if image_name == f"{process_name}.exe".lower():
                result.append(row)
        return result
    except Exception:
        return []


def is_editor_running(process_name: str) -> bool:
    return len(get_tasklist_rows(process_name, verbose=False)) > 0


def extract_project_name(process_name: str):
    rows = get_tasklist_rows(process_name, verbose=True)
    for row in rows:
        title = repair_mojibake((row[8] if len(row) > 8 else "").strip())
        normalized = title.lower().replace(" ", "")
        if not title or normalized in {"n/a", "н/д"}:
            continue
        if "/" in title and len(title) <= 8:
            continue
        if " - " in title:
            name = title.split(" - ", 1)[1].strip()
        elif "-" in title:
            name = title.split("-", 1)[1].strip()
        else:
            continue
        if name:
            return name
    return None


def launch_editor(path: str):
    if os.path.exists(path):
        subprocess.Popen([path], creationflags=0x00000008)
        log(f"Editor launched: {path}")
    else:
        log(f"Editor not found: {path}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    log("RPC launcher starting...")
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    cfg = load_config()
    app_id = str(cfg.get("DiscordApplicationId", "")).strip()
    if not app_id or "PUT_YOUR" in app_id:
        log("Set DiscordApplicationId in discord-rpc-config.json first.")
        return 1

    process_name = cfg.get("TargetProcessName", "LMR Scenario Editor").strip()
    exe_path = cfg.get("TargetExePath", ".\\LMR Scenario Editor.exe").strip()
    auto_launch = bool(cfg.get("AutoLaunchEditor", False))
    auto_exit = bool(cfg.get("AutoExitWhenEditorClosed", True))
    delay = max(0.5, float(cfg.get("LoopDelayMs", 2000)) / 1000.0)

    fallback_details = cfg.get("Details", "Editing scenarios")
    state = cfg.get("State", "LMR Scenario Editor")
    large_image = cfg.get("LargeImageKey", "main_image")
    large_text = cfg.get("LargeImageText", "LMR Scenario Editor")
    small_image = cfg.get("SmallImageKey", "") or None
    small_text = cfg.get("SmallImageText", "") or None

    if not os.path.isabs(exe_path):
        exe_path = os.path.abspath(exe_path)

    if auto_launch:
        launch_editor(exe_path)

    start_ts = int(time.time())

    rpc = Presence(app_id)
    connected = False

    def ensure_connected() -> bool:
        nonlocal connected
        if connected:
            return True
        try:
            rpc.connect()
            connected = True
            log("Discord RPC connected.")
            return True
        except Exception as ex:
            connected = False
            log(f"RPC connect failed: {ex}")
            return False

    presence_sent = False
    last_update = 0.0
    last_project_name = ""

    while True:
        editor_running = is_editor_running(process_name)

        if editor_running:
            project_name = extract_project_name(process_name) or fallback_details
            now = time.time()
            name_changed = project_name != last_project_name
            should_refresh = (not presence_sent) or (now - last_update >= 15) or name_changed

            if should_refresh and ensure_connected():
                try:
                    rpc.update(
                        details=project_name,
                        state=state,
                        start=start_ts,
                        large_image=large_image,
                        large_text=large_text,
                        small_image=small_image,
                        small_text=small_text,
                    )
                    last_update = now
                    if not presence_sent:
                        log("Presence enabled.")
                    if name_changed:
                        log(f"Project name updated: {project_name}")
                    presence_sent = True
                    last_project_name = project_name
                except Exception as ex:
                    connected = False
                    if presence_sent:
                        log(f"Presence refresh failed: {ex}")
                    else:
                        log(f"Presence update failed: {ex}")
                    time.sleep(2)
                    continue

        if not editor_running and presence_sent:
            try:
                rpc.clear()
            except Exception:
                pass
            log("Presence cleared (editor closed).")
            if auto_exit:
                break
            presence_sent = False
            last_project_name = ""
            connected = False

        time.sleep(delay)

    try:
        rpc.close()
    except Exception:
        pass

    log("RPC launcher stopped.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as ex:
        log(f"Fatal launcher error: {ex}")
        sys.exit(1)
