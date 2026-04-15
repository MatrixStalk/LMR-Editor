import csv
import io
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime

from pypresence import Presence

CONFIG_NAME = "discord-rpc-config.json"
LOG_NAME = "rpc-python.log"
FILE_RE = re.compile(r'([^\s\\/:*?"<>|]+\.[A-Za-z0-9]{1,10})')
_UIA_IMPORT_ERROR = None
try:
    import psutil
    from pywinauto import Desktop
except Exception as _ex:
    psutil = None
    Desktop = None
    _UIA_IMPORT_ERROR = str(_ex)


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


def get_editor_window_title(process_name: str):
    rows = get_tasklist_rows(process_name, verbose=True)
    best_title = None
    best_score = -10**9
    for row in rows:
        title = repair_mojibake((row[8] if len(row) > 8 else "").strip())
        normalized = title.lower().replace(" ", "")
        if not title or normalized in {"n/a", "н/д"}:
            continue
        if "/" in title and len(title) <= 8:
            continue
        parts = [p.strip() for p in title.split(" - ") if p.strip()]
        score = len(parts) * 100 + len(title)
        if FILE_RE.search(title):
            score += 250
        if score > best_score:
            best_score = score
            best_title = title
    return best_title


def extract_project_name_from_title(title: str):
    if not title:
        return None
    if " - " in title:
        parts = [p.strip() for p in title.split(" - ") if p.strip()]
        if len(parts) >= 2:
            return parts[1]
        return title.split(" - ", 1)[1].strip() or None
    if "-" in title:
        return title.split("-", 1)[1].strip() or None
    return None


def extract_file_name_from_title(title: str, fallback_state: str):
    if not title:
        return fallback_state
    if " - " in title:
        parts = [p.strip() for p in title.split(" - ") if p.strip()]
        if len(parts) >= 3:
            candidate = os.path.basename(parts[-1].strip("\" "))
            if candidate:
                return candidate
    m = FILE_RE.search(title)
    if m:
        return os.path.basename(m.group(1))
    return fallback_state


def get_active_file_name_from_tabs(process_name: str):
    if Desktop is None or psutil is None:
        return None
    try:
        targets = []
        for p in psutil.process_iter(["pid", "name"]):
            name = (p.info.get("name") or "").lower()
            if name == f"{process_name}.exe".lower():
                targets.append(p.info["pid"])
        if not targets:
            return None

        for pid in targets:
            windows = Desktop(backend="uia").windows(process=pid)
            for w in windows:
                try:
                    tab = w.child_window(auto_id="MainTabControl", control_type="Tab")
                    if not tab.exists(timeout=0):
                        continue
                    tab_wrap = tab.wrapper_object()
                    items = tab_wrap.descendants(control_type="TabItem")
                    for item in items:
                        name = (item.window_text() or "").strip()
                        if not name:
                            continue
                        selected = False
                        try:
                            selected = item.iface_selection_item.CurrentIsSelected
                        except Exception:
                            selected = False
                        if selected:
                            return os.path.basename(name)

                    for item in items:
                        name = (item.window_text() or "").strip()
                        if FILE_RE.search(name):
                            return os.path.basename(FILE_RE.search(name).group(1))

                    buttons = tab_wrap.descendants(control_type="Button")
                    for btn in buttons:
                        name = (btn.window_text() or "").strip()
                        if FILE_RE.search(name):
                            return os.path.basename(FILE_RE.search(name).group(1))
                except Exception:
                    continue
    except Exception:
        return None
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
    fallback_state = cfg.get("State", "LMR Scenario Editor")
    large_image = cfg.get("LargeImageKey", "main_image")
    large_text = cfg.get("LargeImageText", "LMR Scenario Editor")
    small_image = cfg.get("SmallImageKey", "") or None
    small_text = cfg.get("SmallImageText", "") or None

    if not os.path.isabs(exe_path):
        exe_path = os.path.abspath(exe_path)

    if auto_launch:
        launch_editor(exe_path)

    if _UIA_IMPORT_ERROR:
        log(f"UIA tab tracking unavailable: {_UIA_IMPORT_ERROR}")

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
    last_file_name = ""

    while True:
        editor_running = is_editor_running(process_name)

        if editor_running:
            window_title = get_editor_window_title(process_name)
            project_name = extract_project_name_from_title(window_title) or fallback_details
            file_name = (
                get_active_file_name_from_tabs(process_name)
                or extract_file_name_from_title(window_title, fallback_state)
            )
            now = time.time()
            name_changed = project_name != last_project_name
            file_changed = file_name != last_file_name
            should_refresh = (not presence_sent) or (now - last_update >= 15) or name_changed or file_changed

            if should_refresh and ensure_connected():
                try:
                    rpc.update(
                        details=project_name,
                        state=file_name,
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
                    if file_changed:
                        log(f"File name updated: {file_name}")
                    presence_sent = True
                    last_project_name = project_name
                    last_file_name = file_name
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
            last_file_name = ""
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
