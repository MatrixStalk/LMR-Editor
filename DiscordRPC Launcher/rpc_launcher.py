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

    log("RPC launcher starting (safe mode)...")
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
            title = get_editor_window_title(process_name)
            detected_project = extract_project_name_from_title(title)
            detected_file = extract_file_name_from_title(title)

            project_name = detected_project or last_project_name or fallback_details
            file_name = detected_file or last_file_name or fallback_state

            now = time.time()
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
                        src = "title" if detected_file else ("cached" if last_file_name else "fallback")
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
