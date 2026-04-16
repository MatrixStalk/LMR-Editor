import json
import shutil
import struct
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

try:
    from pypresence import Presence
except ImportError:
    Presence = None


BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
DISCORD_RPC_PATH = BASE_DIR / "discordrpc"
LAYOUT_PATH = BASE_DIR / "editor_layout.json"

BACKGROUND_IMAGE_PATH = ASSETS_DIR / "mb_bg.png"
TRANSPARENT_COLOR = "#010203"
TEXT_EXTENSIONS = {".json", ".md", ".py", ".rpy", ".rpym", ".toml", ".txt", ".xml", ".yml", ".yaml"}


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def get_background_size():
    try:
        with BACKGROUND_IMAGE_PATH.open("rb") as stream:
            header = stream.read(24)
        if header[:8] == b"\x89PNG\r\n\x1a\n":
            width, height = struct.unpack(">II", header[16:24])
            return width, height
    except OSError:
        return DEFAULT_LAYOUT["window"]["width"], DEFAULT_LAYOUT["window"]["height"]
    return DEFAULT_LAYOUT["window"]["width"], DEFAULT_LAYOUT["window"]["height"]


def load_discord_rpc_config() -> dict[str, str]:
    default_config = {
        "app_display_name": "SGMEditor",
        "client_id": "1494029959981830144",
        "large_image_key": "sgmeditor",
        "small_image_key": "sgmeditor_small",
    }
    config_path = DISCORD_RPC_PATH / "config.json" if DISCORD_RPC_PATH.is_dir() else DISCORD_RPC_PATH
    config = load_json(config_path, default_config)
    merged = default_config.copy()
    for key in default_config:
        value = config.get(key)
        if isinstance(value, str) and value.strip():
            merged[key] = value.strip()
    return merged


DEFAULT_LAYOUT = {
    "window": {"width": 1919, "height": 1079, "drag_top_height": 52},
    "menu": {"project_x": 148, "file_x": 203, "settings_x": 239, "y": 31},
    "logos": {"main_x": 878, "main_y": 29, "side_x": 108, "side_y": 81},
    "buttons": {
        "open_x": 102,
        "open_y": 66,
        "min_x": 1748,
        "min_y": 31,
        "close_x": 1782,
        "close_y": 24,
    },
    "header": {"x": 136, "y": 93},
    "editor": {"x": 93, "y": 101, "width": 1461, "height": 823},
    "line_numbers": {"x": 58, "y": 101, "width": 28, "height": 823},
    "files": {"x": 1676, "y": 77, "width": 140, "height": 844},
    "status": {"mode_x": 106, "mode_y": 919, "cursor_x": 810, "cursor_y": 919},
}


RPC_CONFIG = load_discord_rpc_config()
APP_DISPLAY_NAME = RPC_CONFIG["app_display_name"]


class DiscordPresenceManager:
    def __init__(self):
        self.client_id = RPC_CONFIG["client_id"]
        self.large_image_key = RPC_CONFIG["large_image_key"]
        self.small_image_key = RPC_CONFIG["small_image_key"]
        self.rpc = None
        self.connected = False
        self.started_at = int(time.time())
        self.last_payload = None

    def connect(self):
        if Presence is None or not self.client_id or self.connected:
            return
        try:
            self.rpc = Presence(self.client_id)
            self.rpc.connect()
            self.connected = True
        except Exception:
            self.rpc = None
            self.connected = False

    def update(self, project_name: str, file_name: str):
        self.last_payload = (project_name, file_name)
        if not self.connected:
            self.connect()
        if not self.connected or self.rpc is None:
            return
        payload = {
            "details": project_name,
            "state": file_name,
            "large_text": APP_DISPLAY_NAME,
            "start": self.started_at,
        }
        if self.large_image_key:
            payload["large_image"] = self.large_image_key
        if self.small_image_key:
            payload["small_image"] = self.small_image_key
            payload["small_text"] = APP_DISPLAY_NAME
        try:
            self.rpc.update(**payload)
        except Exception:
            self.connected = False
            self.rpc = None

    def ensure(self):
        if self.connected or self.last_payload is None:
            return
        self.update(*self.last_payload)

    def clear(self):
        if not self.connected or self.rpc is None:
            return
        try:
            self.rpc.clear()
            self.rpc.close()
        except Exception:
            pass


class EditorApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.layout = self._sanitize_layout(load_json(LAYOUT_PATH, DEFAULT_LAYOUT))
        self.layout_mtime = self._get_layout_mtime()
        self.root.title(APP_DISPLAY_NAME)
        self.root.overrideredirect(True)
        self.root.resizable(False, False)
        self.root.configure(bg=TRANSPARENT_COLOR)
        try:
            self.root.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)
        except tk.TclError:
            pass
        self.root.geometry(self._center_geometry())
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.bind("<Map>", self._handle_window_map)

        self.project_dir: Path | None = None
        self.current_file: Path | None = None
        self.file_paths: list[Path] = []
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        self.assets = self._load_assets()
        self.discord = DiscordPresenceManager()

        self.canvas = None
        self.file_listbox = None
        self.editor_text = None
        self.line_numbers = None
        self.header_id = None
        self.mode_id = None
        self.cursor_id = None
        self.drag_zone_id = None

        self._build_window()
        self._bind_shortcuts()
        self._update_status()
        self._update_presence()
        self._presence_loop()
        self._watch_layout_file()

    def _center_geometry(self):
        width = self.layout["window"]["width"]
        height = self.layout["window"]["height"]
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
        return f"{width}x{height}+{x}+{y}"

    def _load_assets(self):
        assets = {}
        for name in (
            "mb_bg.png",
            "exit_btn_clicked.png",
            "exit_btn_idle.png",
            "exit_btn_onmouse.png",
            "hide_btn_clicked.png",
            "hide_btn_idle.png",
            "hide_btn_onmouse.png",
            "file_choose.png",
            "file_choose_last.png",
            "me_logo.png",
            "sgme_logo.png",
        ):
            path = ASSETS_DIR / name
            if path.exists():
                assets[name] = tk.PhotoImage(file=str(path))
        return assets

    def _build_window(self):
        width = self.layout["window"]["width"]
        height = self.layout["window"]["height"]
        self.canvas = tk.Canvas(self.root, width=width, height=height, bg=TRANSPARENT_COLOR, highlightthickness=0, bd=0)
        self.canvas.pack()
        if "mb_bg.png" in self.assets:
            self.canvas.create_image(0, 0, image=self.assets["mb_bg.png"], anchor="nw")

        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._drag_window)
        self.drag_zone_id = self.canvas.create_rectangle(
            0,
            0,
            width,
            self.layout["window"]["drag_top_height"],
            fill="",
            outline="",
            tags=("drag_zone",),
        )
        self.canvas.tag_bind("drag_zone", "<ButtonPress-1>", self._start_drag)
        self.canvas.tag_bind("drag_zone", "<B1-Motion>", self._drag_window)

        menu = self.layout["menu"]
        self._create_text_button(menu["project_x"], menu["y"], "Project", self.open_project)
        self._create_text_button(menu["file_x"], menu["y"], "File", self.save_current_file)
        self._create_text_button(menu["settings_x"], menu["y"], "Settings", self.export_zip)

        logos = self.layout["logos"]
        if "me_logo.png" in self.assets:
            logo_main = self.canvas.create_image(logos["main_x"], logos["main_y"], image=self.assets["me_logo.png"], anchor="nw")
            self.canvas.tag_bind(logo_main, "<ButtonPress-1>", self._start_drag)
            self.canvas.tag_bind(logo_main, "<B1-Motion>", self._drag_window)
        if "sgme_logo.png" in self.assets:
            logo_side = self.canvas.create_image(logos["side_x"], logos["side_y"], image=self.assets["sgme_logo.png"], anchor="nw")
            self.canvas.tag_bind(logo_side, "<ButtonPress-1>", self._start_drag)
            self.canvas.tag_bind(logo_side, "<B1-Motion>", self._drag_window)

        buttons = self.layout["buttons"]
        self._create_image_button(buttons["open_x"], buttons["open_y"], "file_choose.png", "file_choose_last.png", "file_choose_last.png", self.open_project)
        self._create_image_button(buttons["min_x"], buttons["min_y"], "hide_btn_idle.png", "hide_btn_onmouse.png", "hide_btn_clicked.png", self._minimize_window)
        self._create_image_button(buttons["close_x"], buttons["close_y"], "exit_btn_idle.png", "exit_btn_onmouse.png", "exit_btn_clicked.png", self.on_close)

        header = self.layout["header"]
        self.header_id = self.canvas.create_text(
            header["x"],
            header["y"],
            anchor="nw",
            text="# no file selected",
            fill="#4ce4df",
            font=("Cascadia Mono", 10),
        )

        editor = self.layout["editor"]
        self.editor_text = tk.Text(
            self.root,
            bg=TRANSPARENT_COLOR,
            fg="#d8d8d8",
            insertbackground="#56f4ee",
            selectbackground="#143c3d",
            selectforeground="#ffffff",
            font=("Cascadia Mono", 10),
            bd=0,
            highlightthickness=0,
            relief="flat",
            wrap="none",
            undo=True,
        )
        self.editor_text.bind("<KeyRelease>", lambda _e: self._update_status())
        self.editor_text.bind("<ButtonRelease>", lambda _e: self._update_status())
        self.editor_text.bind("<Control-s>", lambda _e: self.save_current_file())
        self.canvas.create_window(editor["x"], editor["y"], anchor="nw", window=self.editor_text, width=editor["width"], height=editor["height"])

        line_numbers = self.layout["line_numbers"]
        self.line_numbers = tk.Text(
            self.root,
            bg=TRANSPARENT_COLOR,
            fg="#6e6e6e",
            font=("Cascadia Mono", 9),
            bd=0,
            highlightthickness=0,
            relief="flat",
            wrap="none",
            state="disabled",
        )
        self.canvas.create_window(
            line_numbers["x"],
            line_numbers["y"],
            anchor="nw",
            window=self.line_numbers,
            width=line_numbers["width"],
            height=line_numbers["height"],
        )

        files = self.layout["files"]
        self.file_listbox = tk.Listbox(
            self.root,
            bg=TRANSPARENT_COLOR,
            fg="#cfcfcf",
            selectbackground="#10292b",
            selectforeground="#56f4ee",
            font=("Cascadia Mono", 9),
            bd=0,
            highlightthickness=0,
            relief="flat",
            activestyle="none",
            exportselection=False,
        )
        self.file_listbox.bind("<Double-Button-1>", self._open_selected_file)
        self.file_listbox.bind("<Return>", self._open_selected_file)
        self.canvas.create_window(files["x"], files["y"], anchor="nw", window=self.file_listbox, width=files["width"], height=files["height"])

        status = self.layout["status"]
        self.mode_id = self.canvas.create_text(status["mode_x"], status["mode_y"], anchor="nw", text="", fill="#d7d9d7", font=("Segoe UI", 7))
        self.cursor_id = self.canvas.create_text(status["cursor_x"], status["cursor_y"], anchor="nw", text="", fill="#7a8481", font=("Segoe UI", 7))

    def _create_text_button(self, x, y, text, command):
        item = self.canvas.create_text(x, y, anchor="nw", text=text, fill="#d3d7d5", font=("Segoe UI", 9), tags=(f"button_{text}",))
        self.canvas.tag_bind(item, "<Button-1>", lambda _e: command())
        self.canvas.tag_bind(item, "<Enter>", lambda _e, item_id=item: self.canvas.itemconfigure(item_id, fill="#56f4ee"))
        self.canvas.tag_bind(item, "<Leave>", lambda _e, item_id=item: self.canvas.itemconfigure(item_id, fill="#d3d7d5"))
        return item

    def _create_image_button(self, x, y, idle_name, hover_name, pressed_name, command):
        item = self.canvas.create_image(x, y, anchor="nw", image=self.assets.get(idle_name))
        self.canvas.tag_bind(item, "<Enter>", lambda _e, item_id=item: self.canvas.itemconfigure(item_id, image=self.assets.get(hover_name)))
        self.canvas.tag_bind(item, "<Leave>", lambda _e, item_id=item: self.canvas.itemconfigure(item_id, image=self.assets.get(idle_name)))
        self.canvas.tag_bind(item, "<ButtonPress-1>", lambda _e, item_id=item: self.canvas.itemconfigure(item_id, image=self.assets.get(pressed_name)))
        self.canvas.tag_bind(item, "<ButtonRelease-1>", lambda _e, item_id=item: self.canvas.itemconfigure(item_id, image=self.assets.get(hover_name)))
        self.canvas.tag_bind(item, "<Button-1>", lambda _e: command())
        return item

    def _bind_shortcuts(self):
        self.root.bind("<Escape>", lambda _e: self.on_close())
        self.root.bind("<Control-s>", lambda _e: self.save_current_file())

    @staticmethod
    def _deep_update(target, source):
        for key, value in source.items():
            if isinstance(value, dict) and isinstance(target.get(key), dict):
                EditorApp._deep_update(target[key], value)
            else:
                target[key] = value

    @staticmethod
    def _sanitize_layout(raw_layout):
        layout = json.loads(json.dumps(DEFAULT_LAYOUT))
        if isinstance(raw_layout, dict):
            EditorApp._deep_update(layout, raw_layout)

        bg_width, bg_height = get_background_size()
        width = bg_width
        height = bg_height
        layout["window"]["width"] = width
        layout["window"]["height"] = height
        layout["window"]["drag_top_height"] = max(0, min(int(layout["window"].get("drag_top_height", 52)), height))

        for key in ("editor", "line_numbers", "files"):
            block = layout[key]
            block_width = max(10, min(int(block.get("width", DEFAULT_LAYOUT[key]["width"])), width))
            block_height = max(10, min(int(block.get("height", DEFAULT_LAYOUT[key]["height"])), height))
            block_x = max(0, min(int(block.get("x", DEFAULT_LAYOUT[key]["x"])), width - block_width))
            block_y = max(0, min(int(block.get("y", DEFAULT_LAYOUT[key]["y"])), height - block_height))
            block["x"] = block_x
            block["y"] = block_y
            block["width"] = block_width
            block["height"] = block_height

        layout["header"]["x"] = max(0, min(int(layout["header"].get("x", DEFAULT_LAYOUT["header"]["x"])), width - 20))
        layout["header"]["y"] = max(0, min(int(layout["header"].get("y", DEFAULT_LAYOUT["header"]["y"])), height - 20))
        layout["status"]["mode_x"] = max(0, min(int(layout["status"].get("mode_x", DEFAULT_LAYOUT["status"]["mode_x"])), width - 20))
        layout["status"]["mode_y"] = max(0, min(int(layout["status"].get("mode_y", DEFAULT_LAYOUT["status"]["mode_y"])), height - 20))
        layout["status"]["cursor_x"] = max(0, min(int(layout["status"].get("cursor_x", DEFAULT_LAYOUT["status"]["cursor_x"])), width - 20))
        layout["status"]["cursor_y"] = max(0, min(int(layout["status"].get("cursor_y", DEFAULT_LAYOUT["status"]["cursor_y"])), height - 20))

        for name in ("project_x", "file_x", "settings_x"):
            layout["menu"][name] = max(0, min(int(layout["menu"].get(name, DEFAULT_LAYOUT["menu"][name])), width - 20))
        layout["menu"]["y"] = max(0, min(int(layout["menu"].get("y", DEFAULT_LAYOUT["menu"]["y"])), height - 20))

        for key in ("main_x", "side_x"):
            layout["logos"][key] = max(0, min(int(layout["logos"].get(key, DEFAULT_LAYOUT["logos"][key])), width - 20))
        for key in ("main_y", "side_y"):
            layout["logos"][key] = max(0, min(int(layout["logos"].get(key, DEFAULT_LAYOUT["logos"][key])), height - 20))

        for key in ("open_x", "min_x", "close_x"):
            layout["buttons"][key] = max(0, min(int(layout["buttons"].get(key, DEFAULT_LAYOUT["buttons"][key])), width - 20))
        for key in ("open_y", "min_y", "close_y"):
            layout["buttons"][key] = max(0, min(int(layout["buttons"].get(key, DEFAULT_LAYOUT["buttons"][key])), height - 20))

        return layout

    def _get_layout_mtime(self):
        try:
            return LAYOUT_PATH.stat().st_mtime
        except OSError:
            return None

    def _watch_layout_file(self):
        current_mtime = self._get_layout_mtime()
        if current_mtime != self.layout_mtime:
            self.layout_mtime = current_mtime
            self._reload_layout()
        self.root.after(500, self._watch_layout_file)

    def _reload_layout(self):
        cursor_index = self.editor_text.index("insert") if self.editor_text is not None else "1.0"
        editor_content = self.editor_text.get("1.0", "end-1c") if self.editor_text is not None else ""
        file_selection = self.file_listbox.curselection() if self.file_listbox is not None else ()
        current_x = self.root.winfo_x()
        current_y = self.root.winfo_y()

        self.layout = self._sanitize_layout(load_json(LAYOUT_PATH, DEFAULT_LAYOUT))
        self.root.geometry(f"{self.layout['window']['width']}x{self.layout['window']['height']}+{current_x}+{current_y}")

        if self.canvas is not None:
            self.canvas.destroy()

        self._build_window()

        if self.project_dir is not None:
            self._reload_project_files()
            if file_selection and self.file_listbox is not None and file_selection[0] < self.file_listbox.size():
                self.file_listbox.selection_set(file_selection[0])

        if self.current_file is not None and self.editor_text is not None:
            self.editor_text.delete("1.0", "end")
            self.editor_text.insert("1.0", editor_content)
            self.editor_text.mark_set("insert", cursor_index)
            self.editor_text.see(cursor_index)
            self.canvas.itemconfigure(self.header_id, text=f"# {self.current_file.name}")

        self._update_status()

    def _start_drag(self, event):
        if event.y > self.layout["window"]["drag_top_height"]:
            return
        self.drag_offset_x = event.x_root - self.root.winfo_x()
        self.drag_offset_y = event.y_root - self.root.winfo_y()

    def _drag_window(self, event):
        if event.y > self.layout["window"]["drag_top_height"]:
            return
        x = event.x_root - self.drag_offset_x
        y = event.y_root - self.drag_offset_y
        self.root.geometry(f"{self.layout['window']['width']}x{self.layout['window']['height']}+{x}+{y}")

    def _minimize_window(self):
        self.root.overrideredirect(False)
        self.root.iconify()
        self.root.after(200, self._restore_borderless)

    def _restore_borderless(self):
        if self.root.state() == "normal":
            self.root.overrideredirect(True)

    def _handle_window_map(self, _event=None):
        self.root.after(10, self._restore_borderless)

    def open_project(self):
        folder = filedialog.askdirectory(title="Select mod project folder")
        if not folder:
            return
        self.project_dir = Path(folder)
        self._reload_project_files()
        self._update_status()
        self._update_presence()

    def _reload_project_files(self):
        self.file_listbox.delete(0, "end")
        self.file_paths.clear()
        if not self.project_dir or not self.project_dir.exists():
            return
        files = sorted(
            [path for path in self.project_dir.rglob("*") if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS],
            key=lambda path: str(path.relative_to(self.project_dir)).lower(),
        )
        self.file_paths.extend(files)
        for path in files:
            self.file_listbox.insert("end", str(path.relative_to(self.project_dir)))

    def _open_selected_file(self, _event=None):
        selection = self.file_listbox.curselection()
        if not selection:
            return
        path = self.file_paths[selection[0]]
        self.open_file(path)

    def open_file(self, path: Path):
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = path.read_text(encoding="utf-8", errors="replace")
        self.current_file = path
        self.editor_text.delete("1.0", "end")
        self.editor_text.insert("1.0", content)
        self.canvas.itemconfigure(self.header_id, text=f"# {path.name}")
        self._refresh_line_numbers()
        self._update_status()
        self._update_presence()

    def save_current_file(self):
        if self.current_file is None:
            return
        self.current_file.write_text(self.editor_text.get("1.0", "end-1c"), encoding="utf-8")
        self._update_status()

    def export_zip(self):
        if not self.project_dir:
            messagebox.showwarning("No project", "Open a project first.")
            return
        destination = filedialog.asksaveasfilename(
            title="Export project as ZIP",
            initialdir=str(self.project_dir.parent),
            initialfile=self.project_dir.name,
            defaultextension=".zip",
            filetypes=[("ZIP archive", "*.zip")],
        )
        if not destination:
            return
        shutil.make_archive(str(Path(destination).with_suffix("")), "zip", root_dir=self.project_dir)

    def _refresh_line_numbers(self):
        line_count = int(self.editor_text.index("end-1c").split(".")[0])
        data = "\n".join(str(number) for number in range(1, line_count + 1))
        self.line_numbers.config(state="normal")
        self.line_numbers.delete("1.0", "end")
        self.line_numbers.insert("1.0", data)
        self.line_numbers.config(state="disabled")

    def _update_status(self):
        project_name = self.project_dir.name if self.project_dir else "No project open"
        current_name = self.current_file.name if self.current_file else "No file open"
        line, column = self.editor_text.index("insert").split(".")
        self.canvas.itemconfigure(self.mode_id, text=f"Mode: {project_name}")
        self.canvas.itemconfigure(self.cursor_id, text=f"{current_name}   String: {line}   Column: {column}")
        self._refresh_line_numbers()

    def _update_presence(self):
        project_name = self.project_dir.name if self.project_dir else "No project open"
        file_name = self.current_file.name if self.current_file else "No file open"
        self.discord.update(project_name, file_name)

    def _presence_loop(self):
        self.discord.ensure()
        self.root.after(15000, self._presence_loop)

    def on_close(self):
        self.discord.clear()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = EditorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
