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
_TAB_TRACKING_IMPORT_ERROR = None
try:
    import psutil
    from pywinauto import Desktop
except Exception as _ex:
    psutil = None
    Desktop = None
    _TAB_TRACKING_IMPORT_ERROR = str(_ex)

CONFIG_NAME = "discord-rpc-config.json"
LOG_NAME = "rpc-python.log"
FILE_RE = re.compile(r'([^\s\\/:*?"<>|]+\.[A-Za-z0-9]{1,10})')
VALID_EXTS = {
    ".yaml", ".yml", ".json", ".txt", ".xml", ".ini", ".cfg", ".md", ".csv",
    ".rpy", ".py", ".lua", ".js", ".ts", ".cs", ".cpp", ".h", ".hpp",
    ".script", ".sql", ".toml", ".ltx", ".log"
}


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
    ]
    for src, dst in transforms:
        try:
            candidates.append(text.encode(src).decode(dst))
        except Exception:
            pass
    return max(candidates, key=_text_score)


def normalize_file_candidate(candidate: str):
    if not candidate:
        return None
    candidate = os.path.basename(candidate.strip().strip('"\''))
    if not candidate or len(candidate) > 128:
        return None
    ext = os.path.splitext(candidate)[1].lower()
    if ext not in VALID_EXTS:
        return None
    return candidate


def get_tasklist_rows(process_name: str, verbose: bool):
    args = ["tasklist", "/FI", f"IMAGENAME eq {process_name}.exe", "/FO", "CSV"]
    if verbose:
        args.insert(1, "/V")
    try:
        raw = subprocess.check_output(args, creationflags=0x08000000)
        out = decode_tasklist_output(raw)
        rows = list(csv.reader(io.StringIO(out)))
        if len(rows) <= 1:
            return []
        result = []
        for row in rows[1:]:
            if row and (row[0] if len(row) > 0 else "").strip().lower() == f"{process_name}.exe".lower():
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
        title = repair_mojibake((row[-1] if row else "").strip())
        normalized = title.lower().replace(" ", "")
        if not title or normalized in {"n/a", "н/д"}:
            continue
        parts = [p.strip() for p in title.split(" - ") if p.strip()]
        score = len(parts) * 100 + len(title)
        if FILE_RE.search(title):
            score += 200
        if score > best_score:
            best_title = title
            best_score = score
    return best_title


def extract_project_name_from_title(title: str):
    if not title:
        return None
    parts = [p.strip() for p in title.split(" - ") if p.strip()]
    if len(parts) >= 2:
        return parts[1]
    if "-" in title:
        return title.split("-", 1)[1].strip() or None
    return None


def extract_file_name_from_title(title: str):
    if not title:
        return None
    parts = [p.strip() for p in title.split(" - ") if p.strip()]
    # Usually: Scenario Editor - Project - file.ext
    if len(parts) >= 3:
        c = normalize_file_candidate(parts[-1])
        if c:
            return c
    m = FILE_RE.search(title)
    if m:
        return normalize_file_candidate(m.group(1))
    return None


def detect_file_name_from_tab_cautious(process_name: str):
    if Desktop is None or psutil is None:
        return None
    try:
        pids = []
        for p in psutil.process_iter(["pid", "name"]):
            name = (p.info.get("name") or "").lower()
            if name == f"{process_name}.exe".lower():
                pids.append(p.info["pid"])
        if not pids:
            return None

        # Keep it intentionally lightweight: only top-level windows and direct tab children.
        for pid in pids:
            for w in Desktop(backend="uia").windows(process=pid):
                try:
                    tab = w.child_window(auto_id="MainTabControl", control_type="Tab")
                    if not tab.exists(timeout=0):
                        continue
                    tabw = tab.wrapper_object()
                    items = tabw.children(control_type="TabItem")

                    for item in items:
                        try:
                            name = normalize_file_candidate(item.window_text() or "")
                            if not name:
                                continue
                            selected = False
                            try:
                                selected = bool(item.iface_selection_item.CurrentIsSelected)
                            except Exception:
                                selected = False
                            if selected:
                                return name
                        except Exception:
                            continue

                    for item in items:
                        try:
                            name = normalize_file_candidate(item.window_text() or "")
                            if name:
                                return name
                        except Exception:
                            continue
                except Exception:
                    continue
    except Exception:
        return None
    return None


def detect_file_name_from_open_handles(process_name: str):
    if psutil is None:
        return None
    try:
        pids = []
        for p in psutil.process_iter(["pid", "name"]):
            name = (p.info.get("name") or "").lower()
            if name == f"{process_name}.exe".lower():
                pids.append(p.info["pid"])
        if not pids:
            return None

        candidates = []
        for pid in pids:
            try:
                proc = psutil.Process(pid)
                for f in proc.open_files():
                    path = f.path or ""
                    name = normalize_file_candidate(os.path.basename(path))
                    if not name:
                        continue
                    low = path.lower()
                    # Prefer likely user/project files over binaries/resources.
                    score = 0
                    if "\\library\\" in low or "\\win64-" in low:
                        score -= 200
                    if low.endswith((".yaml", ".yml", ".json", ".txt", ".xml", ".rpy", ".lua", ".script", ".ltx")):
                        score += 200
                    if "\\temp\\" in low or "\\windows\\" in low:
                        score -= 80
                    score += len(path) // 8
                    candidates.append((score, name, path))
            except Exception:
                continue
        if candidates:
            candidates.sort(key=lambda x: x[0], reverse=True)
            return candidates[0][1]
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
    delay = max(1.0, float(cfg.get("LoopDelayMs", 2000)) / 1000.0)
    enable_tab_file_tracking = bool(cfg.get("EnableTabFileTracking", True))
    tab_probe_interval = max(1.5, float(cfg.get("TabProbeIntervalMs", 2500)) / 1000.0)

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
    if enable_tab_file_tracking and _TAB_TRACKING_IMPORT_ERROR:
        log(f"Tab tracking disabled (imports failed): {_TAB_TRACKING_IMPORT_ERROR}")
        enable_tab_file_tracking = False

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
    last_tab_probe = 0.0
    last_tab_file = ""

    while True:
        editor_running = is_editor_running(process_name)

        if editor_running:
            title = get_editor_window_title(process_name)
            detected_project = extract_project_name_from_title(title)
            detected_file = extract_file_name_from_title(title)
            detected_file_source = "title" if detected_file else "none"

            now = time.time()
            if not detected_file:
                handle_file = detect_file_name_from_open_handles(process_name)
                if handle_file:
                    detected_file = handle_file
                    detected_file_source = "open_files"

            if not detected_file and enable_tab_file_tracking and (now - last_tab_probe >= tab_probe_interval):
                last_tab_probe = now
                tab_file = detect_file_name_from_tab_cautious(process_name)
                if tab_file:
                    last_tab_file = tab_file
                    detected_file = tab_file
                    detected_file_source = "tab"
            elif not detected_file and last_tab_file:
                detected_file = last_tab_file
                detected_file_source = "tab-cached"

            project_name = detected_project or last_project_name or fallback_details
            file_name = detected_file or last_file_name or fallback_state

            changed = (project_name != last_project_name) or (file_name != last_file_name)
            should_refresh = (not presence_sent) or (now - last_update >= 15) or changed

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
                    if project_name != last_project_name:
                        log(f"Project name updated: {project_name}")
                    if file_name != last_file_name:
                        src = detected_file_source if detected_file else ("cached" if last_file_name else "fallback")
                        log(f"File name updated: {file_name} (source={src})")
                    presence_sent = True
                    last_project_name = project_name
                    last_file_name = file_name
                except Exception as ex:
                    connected = False
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
