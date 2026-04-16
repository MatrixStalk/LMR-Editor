import json
import os
import shutil
import struct
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from pypresence import Presence
except ImportError:
    Presence = None


BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
DISCORD_RPC_PATH = BASE_DIR / "discordrpc"
LAYOUT_PATH = BASE_DIR / "editor_layout.json"
APP_SETTINGS_PATH = BASE_DIR / "app_settings.json"

BACKGROUND_IMAGE_PATH = ASSETS_DIR / "mb_bg.png"
TRANSPARENT_COLOR = "#010203"
PANEL_BACKGROUND = "#090909"
PANEL_LINES_BACKGROUND = "#101010"
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
        pass
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


def load_app_settings():
    default_settings = {
        "auto_reload_layout": True,
        "discord_rpc_enabled": True,
    }
    settings = load_json(APP_SETTINGS_PATH, default_settings)
    merged = default_settings.copy()
    for key, value in settings.items():
        if isinstance(value, bool):
            merged[key] = value
    return merged


DEFAULT_LAYOUT = {
    "window": {"width": 1919, "height": 1079, "drag_top_height": 52},
    "drag_area": {"x": 94, "y": 22, "width": 1720, "height": 92},
    "menu": {"project_x": 148, "file_x": 203, "settings_x": 239, "y": 31},
    "logos": {"main_x": 878, "main_y": 29, "side_x": 108, "side_y": 81},
    "buttons": {
        "open_x": 102,
        "open_y": 66,
        "min_x": 1748,
        "min_y": 31,
        "close_x": 1782,
        "close_y": 24
    },
    "header": {"x": 136, "y": 93},
    "editor": {"x": 180, "y": 101, "width": 1374, "height": 823},
    "line_numbers": {"x": 145, "y": 101, "width": 28, "height": 823},
    "files": {"x": 1658, "y": 77, "width": 170, "height": 844},
    "status": {"mode_x": 106, "mode_y": 919, "cursor_x": 810, "cursor_y": 919},
    "settings_window": {
        "width": 512,
        "height": 512,
        "offset_x": 100,
        "offset_y": 80,
        "drag_x": 18,
        "drag_y": 10,
        "drag_width": 476,
        "drag_height": 56,
        "title_icon_x": 28,
        "title_icon_y": 26,
        "title_x": 154,
        "title_y": 50,
        "tabs_x": 28,
        "tabs_y": 120,
        "tabs_width": 146,
        "tabs_height": 300,
        "tab_step_y": 50,
        "content_x": 196,
        "content_y": 126,
        "content_width": 286,
        "content_height": 290,
        "button_left_x": 196,
        "button_right_x": 294,
        "button_y": 430
    }
}


RPC_CONFIG = load_discord_rpc_config()
APP_DISPLAY_NAME = RPC_CONFIG["app_display_name"]
APP_SETTINGS = load_app_settings()


class DiscordPresenceManager:
    def __init__(self):
        self.client_id = RPC_CONFIG["client_id"]
        self.large_image_key = RPC_CONFIG["large_image_key"]
        self.small_image_key = RPC_CONFIG["small_image_key"]
        self.rpc = None
        self.connected = False
        self.started_at = int(time.time())
        self.last_payload = None
        self.enabled = APP_SETTINGS["discord_rpc_enabled"]

    def connect(self):
        if not self.enabled or Presence is None or not self.client_id or self.connected:
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
        if not self.enabled:
            return
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
        if not self.enabled or self.connected or self.last_payload is None:
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
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        self.assets = self._load_assets()
        self.discord = DiscordPresenceManager()
        self.app_settings = APP_SETTINGS.copy()

        self.canvas = None
        self.file_tree = None
        self.editor_text = None
        self.line_numbers = None
        self.header_id = None
        self.mode_id = None
        self.cursor_id = None
        self.drag_zone_id = None
        self.popup_menus: dict[str, tk.Menu] = {}
        self.tree_item_paths: dict[str, Path] = {}
        self.settings_window = None
        self.settings_canvas = None
        self.settings_vars: dict[str, tk.BooleanVar] = {}
        self.settings_drag_offset_x = 0
        self.settings_drag_offset_y = 0

        self._build_window()
        self._build_popup_menus()
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
            "button_clicked.png",
            "button_idle.png",
            "button_onmouse.png",
            "exit_btn_clicked.png",
            "exit_btn_idle.png",
            "exit_btn_onmouse.png",
            "files.png",
            "hide_btn_clicked.png",
            "hide_btn_idle.png",
            "hide_btn_onmouse.png",
            "file_choose.png",
            "file_choose_last.png",
            "folder.png",
            "me_logo.png",
            "settings.png",
            "settings_bg.png",
            "sgme_logo.png",
        ):
            path = ASSETS_DIR / name
            if path.exists():
                image = tk.PhotoImage(file=str(path))
                if name in {"folder.png", "files.png"}:
                    image = self._fit_icon(image, 24, 24)
                elif name in {"button_clicked.png", "button_idle.png", "button_onmouse.png"}:
                    image = self._fit_icon(image, 208, 44)
                elif name == "settings.png":
                    image = self._fit_icon(image, 96, 96)
                assets[name] = image
        return assets

    def _fit_icon(self, image: tk.PhotoImage, max_width: int, max_height: int):
        width = image.width()
        height = image.height()
        if width <= max_width and height <= max_height:
            return image

        scale_x = max(1, (width + max_width - 1) // max_width)
        scale_y = max(1, (height + max_height - 1) // max_height)
        scale = max(scale_x, scale_y)
        return image.subsample(scale, scale)

    def _configure_tree_style(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Files.Treeview",
            background=PANEL_BACKGROUND,
            fieldbackground=PANEL_BACKGROUND,
            foreground="#f0f0f0",
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
            rowheight=28,
            font=("Segoe UI", 8, "bold"),
        )
        style.map(
            "Files.Treeview",
            background=[("selected", "#23262c")],
            foreground=[("selected", "#ffffff")],
        )
        style.layout("Files.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    def _build_window(self):
        width = self.layout["window"]["width"]
        height = self.layout["window"]["height"]
        self._configure_tree_style()
        self.canvas = tk.Canvas(self.root, width=width, height=height, bg=TRANSPARENT_COLOR, highlightthickness=0, bd=0)
        self.canvas.pack()
        if "mb_bg.png" in self.assets:
            self.canvas.create_image(0, 0, image=self.assets["mb_bg.png"], anchor="nw")

        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._drag_window)
        drag_area = self.layout["drag_area"]
        self.drag_zone_id = self.canvas.create_rectangle(
            drag_area["x"],
            drag_area["y"],
            drag_area["x"] + drag_area["width"],
            drag_area["y"] + drag_area["height"],
            fill="",
            outline="",
            tags=("drag_zone",),
        )
        self.canvas.tag_bind("drag_zone", "<ButtonPress-1>", self._start_drag)
        self.canvas.tag_bind("drag_zone", "<B1-Motion>", self._drag_window)

        menu = self.layout["menu"]
        self._create_text_button(menu["project_x"], menu["y"], "Project", self.open_project)
        self._create_text_button(menu["file_x"], menu["y"], "File", self.save_current_file)
        self._create_text_button(menu["settings_x"], menu["y"], "Settings", self.open_settings_window)

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
            bg=PANEL_BACKGROUND,
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
            bg=PANEL_LINES_BACKGROUND,
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
        self.file_tree = ttk.Treeview(self.root, show="tree", selectmode="browse", style="Files.Treeview")
        self.file_tree.bind("<Double-Button-1>", self._open_selected_file)
        self.file_tree.bind("<Return>", self._open_selected_file)
        self.canvas.create_window(files["x"], files["y"], anchor="nw", window=self.file_tree, width=files["width"], height=files["height"])

        status = self.layout["status"]
        self.mode_id = self.canvas.create_text(status["mode_x"], status["mode_y"], anchor="nw", text="", fill="#d7d9d7", font=("Segoe UI", 7))
        self.cursor_id = self.canvas.create_text(status["cursor_x"], status["cursor_y"], anchor="nw", text="", fill="#7a8481", font=("Segoe UI", 7))

    def _build_popup_menus(self):
        self.popup_menus = {}

        project_menu = tk.Menu(self.root, tearoff=False, bg="#111111", fg="#d8d8d8", activebackground="#143c3d", activeforeground="#56f4ee", bd=0)
        project_menu.add_command(label="Open Project", command=self.open_project)
        project_menu.add_command(label="Reload Files", command=self._reload_project_files)
        self.popup_menus["Project"] = project_menu

        file_menu = tk.Menu(self.root, tearoff=False, bg="#111111", fg="#d8d8d8", activebackground="#143c3d", activeforeground="#56f4ee", bd=0)
        file_menu.add_command(label="Save", command=self.save_current_file)
        file_menu.add_command(label="Export ZIP", command=self.export_zip)
        file_menu.add_separator()
        file_menu.add_command(label="Close", command=self.on_close)
        self.popup_menus["File"] = file_menu

    def _create_text_button(self, x, y, text, command):
        item = self.canvas.create_text(x, y, anchor="nw", text=text, fill="#d3d7d5", font=("Segoe UI", 9), tags=(f"button_{text}",))
        if text == "Settings":
            self.canvas.tag_bind(item, "<Button-1>", lambda _event, callback=command: callback())
        else:
            self.canvas.tag_bind(item, "<Button-1>", lambda event, label=text, fallback=command: self._show_top_menu(event, label, fallback))
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

    def _show_top_menu(self, event, label, fallback_command):
        menu = self.popup_menus.get(label)
        if menu is None:
            fallback_command()
            return
        try:
            menu.tk_popup(event.x_root, event.y_root + 12)
        finally:
            menu.grab_release()

    def _open_path_in_system(self, path: Path):
        if not path.exists():
            messagebox.showwarning("Not found", f"Path does not exist:\n{path}")
            return
        try:
            os.startfile(str(path))
        except OSError as error:
            messagebox.showerror("Open failed", str(error))

    def open_settings_window(self):
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.lift()
            self.settings_window.focus_force()
            return

        layout = self.layout["settings_window"]
        width = layout["width"]
        height = layout["height"]

        self.settings_window = tk.Toplevel(self.root)
        self.settings_window.title("Settings")
        self.settings_window.transient(self.root)
        self.settings_window.resizable(False, False)
        self.settings_window.configure(bg="#111111")
        self.settings_window.overrideredirect(True)
        self.settings_window.geometry(f"{width}x{height}+{self.root.winfo_x() + layout['offset_x']}+{self.root.winfo_y() + layout['offset_y']}")
        self.settings_window.protocol("WM_DELETE_WINDOW", self.close_settings_window)
        self.settings_window.bind("<Escape>", lambda _e: self.close_settings_window())

        self.settings_canvas = tk.Canvas(self.settings_window, width=width, height=height, bg="#111111", highlightthickness=0, bd=0)
        self.settings_canvas.pack()
        if "settings_bg.png" in self.assets:
            self.settings_canvas.create_image(0, 0, image=self.assets["settings_bg.png"], anchor="nw")
        if "settings.png" in self.assets:
            self.settings_canvas.create_image(layout["title_icon_x"], layout["title_icon_y"], image=self.assets["settings.png"], anchor="nw")

        self.settings_drag_zone = self.settings_canvas.create_rectangle(
            layout["drag_x"],
            layout["drag_y"],
            layout["drag_x"] + layout["drag_width"],
            layout["drag_y"] + layout["drag_height"],
            fill="",
            outline="",
            tags=("settings_drag_zone",),
        )
        self.settings_canvas.tag_bind("settings_drag_zone", "<ButtonPress-1>", self._start_settings_drag)
        self.settings_canvas.tag_bind("settings_drag_zone", "<B1-Motion>", self._drag_settings_window)

        self.settings_canvas.create_text(layout["title_x"], layout["title_y"], anchor="nw", text="Application Settings", fill="#56f4ee", font=("Segoe UI", 15, "bold"))

        self.settings_vars["auto_reload_layout"] = tk.BooleanVar(value=self.app_settings["auto_reload_layout"])
        self.settings_vars["discord_rpc_enabled"] = tk.BooleanVar(value=self.app_settings["discord_rpc_enabled"])
        self.settings_content = tk.Frame(self.settings_window, bg="#111111", bd=0, highlightthickness=0)
        self.settings_canvas.create_window(
            layout["content_x"],
            layout["content_y"],
            anchor="nw",
            window=self.settings_content,
            width=layout["content_width"],
            height=layout["content_height"],
        )

        self.settings_tabs = {}
        tabs = [
            ("General", self._render_general_settings_tab),
            ("Files", self._render_files_settings_tab),
            ("Discord", self._render_discord_settings_tab),
            ("Advanced", self._render_advanced_settings_tab),
        ]
        for index, (label, callback) in enumerate(tabs):
            tab_y = layout["tabs_y"] + index * layout["tab_step_y"]
            tab_item = self.settings_canvas.create_text(layout["tabs_x"], tab_y, anchor="nw", text=label, fill="#cfd4d8", font=("Segoe UI", 10, "bold"))
            self.settings_tabs[label] = tab_item
            self.settings_canvas.tag_bind(tab_item, "<Button-1>", lambda _e, name=label, cb=callback: self._select_settings_tab(name, cb))
            self.settings_canvas.tag_bind(tab_item, "<Enter>", lambda _e, item_id=tab_item: self.settings_canvas.itemconfigure(item_id, fill="#56f4ee"))
            self.settings_canvas.tag_bind(tab_item, "<Leave>", lambda _e, name=label, item_id=tab_item: self.settings_canvas.itemconfigure(item_id, fill="#56f4ee" if getattr(self, "active_settings_tab", "") == name else "#cfd4d8"))

        self._create_settings_button(layout["button_left_x"], layout["button_y"], "Close", self.close_settings_window)
        self._create_settings_button(layout["button_right_x"], layout["button_y"], "Save Settings", self._save_settings)
        self._select_settings_tab("General", self._render_general_settings_tab)

    def _create_settings_button(self, x, y, text, command):
        width = 208
        height = 44
        canvas = tk.Canvas(self.settings_window, width=width, height=height, bg="#111111", highlightthickness=0, bd=0)
        self._set_settings_button_state(canvas, "button_idle.png", text)
        canvas.bind("<Enter>", lambda _e, widget=canvas: self._set_settings_button_state(widget, "button_onmouse.png", text))
        canvas.bind("<Leave>", lambda _e, widget=canvas: self._set_settings_button_state(widget, "button_idle.png", text))
        canvas.bind("<ButtonPress-1>", lambda _e, widget=canvas: self._set_settings_button_state(widget, "button_clicked.png", text))
        canvas.bind("<ButtonRelease-1>", lambda _e, widget=canvas, action=command: (self._set_settings_button_state(widget, "button_onmouse.png", text), action()))
        self.settings_canvas.create_window(x, y, anchor="nw", window=canvas, width=width, height=height)

    def _set_settings_button_state(self, canvas, image_name, text):
        canvas.delete("all")
        if image_name in self.assets:
            canvas.create_image(0, 0, image=self.assets[image_name], anchor="nw")
        canvas.create_text(104, 22, text=text, fill="#f0f0f0", font=("Segoe UI", 9, "bold"))

    def _clear_settings_content(self):
        if self.settings_content is None:
            return
        for child in self.settings_content.winfo_children():
            child.destroy()

    def _start_settings_drag(self, event):
        self.settings_drag_offset_x = event.x_root - self.settings_window.winfo_x()
        self.settings_drag_offset_y = event.y_root - self.settings_window.winfo_y()

    def _drag_settings_window(self, event):
        x = event.x_root - self.settings_drag_offset_x
        y = event.y_root - self.settings_drag_offset_y
        self.settings_window.geometry(f"+{x}+{y}")

    def _select_settings_tab(self, name, render_callback):
        self.active_settings_tab = name
        for tab_name, item_id in self.settings_tabs.items():
            self.settings_canvas.itemconfigure(item_id, fill="#56f4ee" if tab_name == name else "#cfd4d8")
        self._clear_settings_content()
        render_callback()

    def _render_general_settings_tab(self):
        tk.Label(self.settings_content, text="General", bg="#111111", fg="#56f4ee", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(6, 18))
        row = tk.Frame(self.settings_content, bg="#111111")
        row.pack(anchor="w")
        tk.Checkbutton(row, variable=self.settings_vars["auto_reload_layout"], bg="#111111", activebackground="#111111", selectcolor="#111111", fg="#56f4ee", bd=0, highlightthickness=0).pack(side="left")
        tk.Label(row, text="Auto reload layout JSON", bg="#111111", fg="#e6e6e6", font=("Segoe UI", 10)).pack(side="left", padx=(8, 0))

    def _render_files_settings_tab(self):
        tk.Label(self.settings_content, text="Files", bg="#111111", fg="#56f4ee", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(6, 18))
        tk.Label(self.settings_content, text="Open editable config files for the editor.", bg="#111111", fg="#d6d6d6", font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 16))
        self._create_inline_settings_button(self.settings_content, "Open Layout JSON", lambda: self._open_path_in_system(LAYOUT_PATH))
        self._create_inline_settings_button(self.settings_content, "Open App Settings", lambda: self._open_path_in_system(APP_SETTINGS_PATH))

    def _render_discord_settings_tab(self):
        tk.Label(self.settings_content, text="Discord", bg="#111111", fg="#56f4ee", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(6, 18))
        row = tk.Frame(self.settings_content, bg="#111111")
        row.pack(anchor="w")
        tk.Checkbutton(row, variable=self.settings_vars["discord_rpc_enabled"], bg="#111111", activebackground="#111111", selectcolor="#111111", fg="#56f4ee", bd=0, highlightthickness=0).pack(side="left")
        tk.Label(row, text="Enable Discord RPC", bg="#111111", fg="#e6e6e6", font=("Segoe UI", 10)).pack(side="left", padx=(8, 0))
        self._create_inline_settings_button(self.settings_content, "Open RPC Config", lambda: self._open_path_in_system(DISCORD_RPC_PATH / "config.json"))

    def _render_advanced_settings_tab(self):
        tk.Label(self.settings_content, text="Advanced", bg="#111111", fg="#56f4ee", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(6, 18))
        tk.Label(self.settings_content, text="Runtime actions and maintenance tools.", bg="#111111", fg="#d6d6d6", font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 16))
        self._create_inline_settings_button(self.settings_content, "Reload Layout", self._reload_layout)

    def _create_inline_settings_button(self, parent, text, command):
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg="#23262c",
            fg="#f0f0f0",
            activebackground="#2f343b",
            activeforeground="#56f4ee",
            relief="flat",
            bd=0,
            padx=12,
            pady=6,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        )
        button.pack(anchor="w", pady=(0, 10))

    def _save_settings(self):
        self.app_settings["auto_reload_layout"] = bool(self.settings_vars["auto_reload_layout"].get())
        self.app_settings["discord_rpc_enabled"] = bool(self.settings_vars["discord_rpc_enabled"].get())
        APP_SETTINGS_PATH.write_text(json.dumps(self.app_settings, indent=2), encoding="utf-8")
        self.discord.enabled = self.app_settings["discord_rpc_enabled"]
        if not self.discord.enabled:
            self.discord.clear()
            self.discord.connected = False
            self.discord.rpc = None
        else:
            self._update_presence()
        self.close_settings_window()

    def close_settings_window(self):
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.destroy()
        self.settings_window = None
        self.settings_canvas = None

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

        drag_area = layout.get("drag_area", DEFAULT_LAYOUT["drag_area"])
        drag_width = max(10, min(int(drag_area.get("width", DEFAULT_LAYOUT["drag_area"]["width"])), width))
        drag_height = max(10, min(int(drag_area.get("height", DEFAULT_LAYOUT["drag_area"]["height"])), height))
        drag_x = max(0, min(int(drag_area.get("x", DEFAULT_LAYOUT["drag_area"]["x"])), width - drag_width))
        drag_y = max(0, min(int(drag_area.get("y", DEFAULT_LAYOUT["drag_area"]["y"])), height - drag_height))
        layout["drag_area"] = {"x": drag_x, "y": drag_y, "width": drag_width, "height": drag_height}

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

        settings = layout["settings_window"]
        default_settings = DEFAULT_LAYOUT["settings_window"]
        settings["width"] = max(320, int(settings.get("width", default_settings["width"])))
        settings["height"] = max(280, int(settings.get("height", default_settings["height"])))
        settings["offset_x"] = int(settings.get("offset_x", default_settings["offset_x"]))
        settings["offset_y"] = int(settings.get("offset_y", default_settings["offset_y"]))
        for key in ("title_icon_x", "title_icon_y", "title_x", "title_y", "tabs_x", "tabs_y", "content_x", "content_y", "button_left_x", "button_right_x", "button_y"):
            settings[key] = int(settings.get(key, default_settings[key]))
        for key in ("tabs_width", "tabs_height", "tab_step_y", "content_width", "content_height"):
            settings[key] = max(10, int(settings.get(key, default_settings[key])))

        return layout

    def _get_layout_mtime(self):
        try:
            return LAYOUT_PATH.stat().st_mtime
        except OSError:
            return None

    def _watch_layout_file(self):
        current_mtime = self._get_layout_mtime()
        if self.app_settings.get("auto_reload_layout", True) and current_mtime != self.layout_mtime:
            self.layout_mtime = current_mtime
            self._reload_layout()
        self.root.after(500, self._watch_layout_file)

    def _reload_layout(self):
        cursor_index = self.editor_text.index("insert") if self.editor_text is not None else "1.0"
        editor_content = self.editor_text.get("1.0", "end-1c") if self.editor_text is not None else ""
        selected_path = None
        if self.file_tree is not None:
            selection = self.file_tree.selection()
            if selection:
                selected_path = self.tree_item_paths.get(selection[0])
        current_x = self.root.winfo_x()
        current_y = self.root.winfo_y()

        self.layout = self._sanitize_layout(load_json(LAYOUT_PATH, DEFAULT_LAYOUT))
        self.root.geometry(f"{self.layout['window']['width']}x{self.layout['window']['height']}+{current_x}+{current_y}")

        if self.canvas is not None:
            self.canvas.destroy()

        self._build_window()
        self._build_popup_menus()

        if self.project_dir is not None:
            self._reload_project_files()
            if selected_path is not None and self.file_tree is not None:
                for item_id, path in self.tree_item_paths.items():
                    if path == selected_path:
                        self.file_tree.selection_set(item_id)
                        self.file_tree.focus(item_id)
                        break

        if self.current_file is not None and self.editor_text is not None:
            self.editor_text.delete("1.0", "end")
            self.editor_text.insert("1.0", editor_content)
            self.editor_text.mark_set("insert", cursor_index)
            self.editor_text.see(cursor_index)
            self.canvas.itemconfigure(self.header_id, text=f"# {self.current_file.name}")

        self._update_status()

    def _start_drag(self, event):
        drag_area = self.layout["drag_area"]
        if not (drag_area["x"] <= event.x <= drag_area["x"] + drag_area["width"] and drag_area["y"] <= event.y <= drag_area["y"] + drag_area["height"]):
            return
        self.drag_offset_x = event.x_root - self.root.winfo_x()
        self.drag_offset_y = event.y_root - self.root.winfo_y()

    def _drag_window(self, event):
        drag_area = self.layout["drag_area"]
        if not (drag_area["x"] <= event.x <= drag_area["x"] + drag_area["width"] and drag_area["y"] <= event.y <= drag_area["y"] + drag_area["height"]):
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
        if self.file_tree is None:
            return
        self.file_tree.delete(*self.file_tree.get_children())
        self.tree_item_paths.clear()
        if not self.project_dir or not self.project_dir.exists():
            return
        self._insert_tree_node("", self.project_dir)

    def _insert_tree_node(self, parent_id, path: Path):
        if not path.is_dir() and path.suffix.lower() not in TEXT_EXTENSIONS:
            return
        icon = self.assets.get("folder.png" if path.is_dir() else "files.png")
        item_id = self.file_tree.insert(parent_id, "end", text=f"  {path.name}", image=icon, open=(path == self.project_dir))
        self.tree_item_paths[item_id] = path
        if path.is_dir():
            for child in sorted(path.iterdir(), key=lambda item: (item.is_file(), item.name.lower())):
                self._insert_tree_node(item_id, child)

    def _open_selected_file(self, _event=None):
        if self.file_tree is None:
            return
        selection = self.file_tree.selection()
        if not selection:
            return
        item_id = selection[0]
        path = self.tree_item_paths.get(item_id)
        if path is None:
            return
        if path.is_dir():
            self.file_tree.item(item_id, open=not self.file_tree.item(item_id, "open"))
            return
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
        self.close_settings_window()
        self.discord.clear()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = EditorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
