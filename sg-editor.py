import json
import os
import shutil
import struct
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

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
    "file_tabs": {
        "x": 180,
        "y": 101,
        "gap": 6,
        "height": 34,
        "middle_min_width": 100,
        "text_padding_x": 18,
        "active_text_color": "#4ce4df",
        "inactive_text_color": "#d7d9d7",
        "close_padding_right": 12,
        "close_color_active": "#4ce4df",
        "close_color_inactive": "#d7d9d7",
    },
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
        "alpha": 1.0,
        "offset_x": 100,
        "offset_y": 80,
        "bg_x": 0,
        "bg_y": 0,
        "bg_width": 512,
        "bg_height": 512,
        "drag_x": 18,
        "drag_y": 10,
        "drag_width": 476,
        "drag_height": 56,
        "close_x": 474,
        "close_y": 10,
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
        "texts": {
            "top_x": 256,
            "top_y": 160,
            "middle_x": 256,
            "middle_y": 314,
            "discord_x": 256,
            "discord_y": 470,
            "bottom_x": 256,
            "bottom_y": 570
        },
        "action_buttons": {
            "open_rpc_config": {"width": 90, "height": 22, "alpha": 1.0},
            "open_layout_json": {"width": 110, "height": 22, "alpha": 1.0},
            "reload_layout": {"width": 90, "height": 22, "alpha": 1.0},
            "open_app_settings": {"width": 110, "height": 22, "alpha": 1.0},
            "save_settings": {"width": 80, "height": 22, "alpha": 1.0},
            "reset_layout": {"width": 130, "height": 22, "alpha": 1.0},
            "reset_app_settings": {"width": 120, "height": 22, "alpha": 1.0}
        },
        "logos": {
            "lunar_x": 196,
            "lunar_y": 278,
            "python_x": 196,
            "python_y": 566,
            "soviet_games_x": 416,
            "soviet_games_y": 552,
            "soviet_games_width": 96,
            "soviet_games_height": 100
        },
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
        self.open_files: list[Path] = []
        self.file_buffers: dict[Path, str] = {}
        self.dirty_files: set[Path] = set()
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        self.assets = self._load_assets()
        self.resized_asset_cache = {}
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
        self.settings_tab_items = {}
        self.settings_content_items = []
        self.settings_window_bg = None
        self.settings_soviet_games_logo = None
        self.settings_action_widgets = []
        self.file_tab_widgets = []
        self.file_tab_window_ids = []
        self.file_tab_render_job = None
        self.hovered_tree_item = None
        self.last_line_count = 0

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
            "button_border_left_clicked.png",
            "button_border_left_idle.png",
            "button_border_left_onmouse.png",
            "button_border_right_clicked.png",
            "button_border_right_idle.png",
            "button_border_right_onmouse.png",
            "button_middle_clicked.png",
            "button_middle_idle.png",
            "button_middle_onmouse.png",
            "checkbox_off.png",
            "checkbox_on.png",
            "checkbox_onmouse.png",
            "exit_btn_clicked.png",
            "exit_btn_idle.png",
            "exit_btn_onmouse.png",
            "files.png",
            "hide_btn_clicked.png",
            "hide_btn_idle.png",
            "hide_btn_onmouse.png",
            "folder.png",
            "lunar_avatar.png",
            "me_logo.png",
            "py_logo.png",
            "settings.png",
            "settings_bg.png",
            "sg_logo.png",
            "sgme_logo.png",
            "tab_inactive_l.png",
            "tab_inactive_m.png",
            "tab_inactive_r.png",
            "tab_onmouse_l.png",
            "tab_onmouse_m.png",
            "tab_onmouse_r.png",
            "tab_selected_l.png",
            "tab_selected_m.png",
            "tab_selected_r.png",
        ):
            path = ASSETS_DIR / name
            if path.exists():
                image = self._load_image_asset(path)
                if name in {"folder.png", "files.png"}:
                    image = self._fit_icon(image, 24, 24)
                elif name in {"button_clicked.png", "button_idle.png", "button_onmouse.png"}:
                    image = self._fit_icon(image, 208, 44)
                elif name in {"checkbox_off.png", "checkbox_on.png", "checkbox_onmouse.png"}:
                    image = self._fit_icon(image, 18, 18)
                elif name == "settings.png":
                    image = self._fit_icon(image, 96, 96)
                elif name == "lunar_avatar.png":
                    image = self._fit_icon(image, 110, 136)
                elif name == "py_logo.png":
                    image = self._fit_icon(image, 96, 54)
                elif name == "sg_logo.png":
                    image = self._fit_icon(image, 96, 100)
                assets[name] = image
        return assets

    def _load_image_asset(self, path: Path):
        if Image is not None and ImageTk is not None:
            with Image.open(path) as source:
                return ImageTk.PhotoImage(source.convert("RGBA"))
        return tk.PhotoImage(file=str(path))

    def _fit_icon(self, image, max_width: int, max_height: int):
        width = image.width()
        height = image.height()
        if width <= max_width and height <= max_height:
            return image

        if Image is not None and ImageTk is not None:
            pil_image = ImageTk.getimage(image)
            resized = pil_image.copy()
            resized.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(resized)

        scale_x = max(1, (width + max_width - 1) // max_width)
        scale_y = max(1, (height + max_height - 1) // max_height)
        scale = max(scale_x, scale_y)
        return image.subsample(scale, scale)

    def _resize_image_exact(self, image, width: int, height: int):
        width = max(1, int(width))
        height = max(1, int(height))
        if image.width() == width and image.height() == height:
            return image

        if Image is not None and ImageTk is not None:
            pil_image = ImageTk.getimage(image)
            resized = pil_image.resize((width, height), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(resized)

        source_width = max(1, image.width())
        source_height = max(1, image.height())
        return image.zoom(width, height).subsample(source_width, source_height)

    def _load_asset_exact(self, name: str, width: int, height: int):
        path = ASSETS_DIR / name
        if not path.exists():
            return None

        width = max(1, int(width))
        height = max(1, int(height))

        if Image is not None and ImageTk is not None:
            with Image.open(path) as source:
                resized = source.convert("RGBA").resize((width, height), Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(resized)

        return self._resize_image_exact(tk.PhotoImage(file=str(path)), width, height)

    def _load_asset_exact_alpha(self, name: str, width: int, height: int, alpha: float):
        path = ASSETS_DIR / name
        if not path.exists():
            return None

        width = max(1, int(width))
        height = max(1, int(height))
        alpha = max(0.0, min(float(alpha), 1.0))

        if Image is not None and ImageTk is not None:
            with Image.open(path) as source:
                resized = source.convert("RGBA").resize((width, height), Image.Resampling.LANCZOS)
                if alpha < 1.0:
                    r, g, b, a = resized.split()
                    a = a.point(lambda value: int(value * alpha))
                    resized = Image.merge("RGBA", (r, g, b, a))
                return ImageTk.PhotoImage(resized)

        return self._load_asset_exact(name, width, height)

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
        self._create_image_button(buttons["min_x"], buttons["min_y"], "hide_btn_idle.png", "hide_btn_onmouse.png", "hide_btn_clicked.png", self._minimize_window)
        self._create_image_button(buttons["close_x"], buttons["close_y"], "exit_btn_idle.png", "exit_btn_onmouse.png", "exit_btn_clicked.png", self.on_close)

        self.header_id = None
        self._render_file_tabs()

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
        self.editor_text.bind("<Button-1>", lambda _e: self.editor_text.focus_set())
        self.editor_text.bind("<KeyRelease>", self._handle_editor_key_release)
        self.editor_text.bind("<ButtonRelease>", lambda _e: self._update_status(refresh_lines=False))
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
        self.file_tree.bind("<Motion>", self._handle_file_tree_hover)
        self.file_tree.bind("<Leave>", self._clear_file_tree_hover)
        self.file_tree.tag_configure("hover", background="#143c3d", foreground="#56f4ee")
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

    def _is_file_dirty(self, path: Path) -> bool:
        return path in self.dirty_files

    def _update_current_buffer(self):
        if self.current_file is None or self.editor_text is None:
            return
        self.file_buffers[self.current_file] = self.editor_text.get("1.0", "end-1c")
        self.dirty_files.add(self.current_file)

    def _handle_editor_key_release(self, _event=None):
        self._update_current_buffer()
        self._update_status(refresh_lines=True)
        self._request_render_file_tabs()

    def _set_tree_item_hover(self, item_id):
        if self.file_tree is None:
            return
        if self.hovered_tree_item and self.file_tree.exists(self.hovered_tree_item):
            current_tags = tuple(tag for tag in self.file_tree.item(self.hovered_tree_item, "tags") if tag != "hover")
            self.file_tree.item(self.hovered_tree_item, tags=current_tags)
        self.hovered_tree_item = None
        if item_id and self.file_tree.exists(item_id):
            current_tags = tuple(tag for tag in self.file_tree.item(item_id, "tags") if tag != "hover")
            self.file_tree.item(item_id, tags=current_tags + ("hover",))
            self.hovered_tree_item = item_id

    def _handle_file_tree_hover(self, event):
        if self.file_tree is None:
            return
        item_id = self.file_tree.identify_row(event.y)
        self._set_tree_item_hover(item_id)

    def _clear_file_tree_hover(self, _event=None):
        self._set_tree_item_hover(None)

    def _clear_file_tabs(self):
        self.file_tab_render_job = None
        if self.canvas is not None:
            for item_id in self.file_tab_window_ids:
                try:
                    self.canvas.delete(item_id)
                except tk.TclError:
                    pass
        self.file_tab_window_ids.clear()
        for widget in self.file_tab_widgets:
            try:
                widget.destroy()
            except tk.TclError:
                pass
        self.file_tab_widgets.clear()

    def _request_render_file_tabs(self):
        if self.root is None:
            return
        if self.file_tab_render_job is not None:
            return

        def _run():
            self.file_tab_render_job = None
            self._render_file_tabs()

        self.file_tab_render_job = self.root.after_idle(_run)

    def _render_file_tabs(self):
        if self.canvas is None:
            return
        self._clear_file_tabs()
        layout = self.layout["file_tabs"]
        x = layout["x"]
        y = layout["y"]
        gap = layout["gap"]
        height = layout["height"]
        for path in self.open_files:
            tab = self._create_file_tab_widget(path, height)
            total_width = tab.winfo_reqwidth()
            self.file_tab_widgets.append(tab)
            item_id = self.canvas.create_window(x, y, anchor="nw", window=tab, width=total_width, height=height)
            self.file_tab_window_ids.append(item_id)
            x += total_width + gap

    def _create_file_tab_widget(self, path: Path, height: int):
        layout = self.layout["file_tabs"]
        label = f"* {path.name}" if self._is_file_dirty(path) else path.name
        state = "selected" if path == self.current_file else "inactive"
        left_idle = self.assets.get(f"tab_{state}_l.png")
        right_idle = self.assets.get(f"tab_{state}_r.png")
        left_width = max(1, int(round(left_idle.width() * (height / max(1, left_idle.height()))))) if left_idle else 10
        right_width = max(1, int(round(right_idle.width() * (height / max(1, right_idle.height()))))) if right_idle else 10
        close_reserved = layout["close_padding_right"] + 12
        estimated_middle = max(layout["middle_min_width"], len(label) * 8 + layout["text_padding_x"] * 2 + close_reserved)
        total_width = left_width + estimated_middle + right_width
        widget = tk.Canvas(self.root, width=total_width, height=height, bg=PANEL_BACKGROUND, highlightthickness=0, bd=0)
        widget._images = {}  # type: ignore[attr-defined]

        def build_state(state_name: str):
            left = self._load_asset_exact(f"tab_{state_name}_l.png", left_width, height)
            middle = self._load_asset_exact(f"tab_{state_name}_m.png", estimated_middle, height)
            right = self._load_asset_exact(f"tab_{state_name}_r.png", right_width, height)
            if left is None or middle is None or right is None:
                return
            widget._images[state_name] = (left, middle, right)  # type: ignore[attr-defined]

        for state_name in ("inactive", "onmouse", "selected"):
            build_state(state_name)

        def draw_state(state_name: str):
            images = widget._images.get(state_name)  # type: ignore[attr-defined]
            if images is None:
                return
            left, middle, right = images
            text_color = layout["active_text_color"] if path == self.current_file else layout["inactive_text_color"]
            close_color = layout["close_color_active"] if path == self.current_file else layout["close_color_inactive"]
            widget.delete("all")
            widget.create_rectangle(0, 0, total_width, height, fill=PANEL_BACKGROUND, outline=PANEL_BACKGROUND)
            widget.create_image(0, 0, image=left, anchor="nw")
            widget.create_image(left_width, 0, image=middle, anchor="nw")
            widget.create_image(left_width + estimated_middle, 0, image=right, anchor="nw")
            widget.create_text((total_width - close_reserved) // 2, height // 2, text=label, fill=text_color, font=("Cascadia Mono", 9, "bold"))
            close_item = widget.create_text(
                total_width - layout["close_padding_right"],
                height // 2,
                text="x",
                fill=close_color,
                font=("Cascadia Mono", 9, "bold"),
            )
            widget.tag_bind(close_item, "<Enter>", lambda _e, p=path: draw_state("selected" if p == self.current_file else "onmouse"))
            def handle_close(_event=None, p=path):
                self.close_file_tab(p)
                return "break"
            widget.tag_bind(close_item, "<Button-1>", handle_close)

        draw_state(state)
        widget.bind("<Enter>", lambda _e, p=path: draw_state("selected" if p == self.current_file else "onmouse"))
        widget.bind("<Leave>", lambda _e, p=path: draw_state("selected" if p == self.current_file else "inactive"))
        widget.bind("<Button-1>", lambda _e, p=path: self.switch_to_file(p))
        return widget
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
        self.root.bind("<Control-s>", lambda _e: (self.save_current_file(), "break"))
        self.root.bind("<Control-z>", lambda _e: (self.editor_text.edit_undo() if self.editor_text else None, self._handle_editor_key_release(), "break"))
        self.root.bind("<Control-y>", lambda _e: (self.editor_text.edit_redo() if self.editor_text else None, self._handle_editor_key_release(), "break"))
        self.root.bind("<Control-Shift-Z>", lambda _e: (self.editor_text.edit_redo() if self.editor_text else None, self._handle_editor_key_release(), "break"))
        self.root.bind("<Control-o>", lambda _e: (self.open_project(), "break"))
        self.root.bind("<Control-w>", lambda _e: (self.close_file_tab(self.current_file) if self.current_file else None, "break"))

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
            try:
                self.settings_window.deiconify()
            except tk.TclError:
                pass
            try:
                self.settings_window.wm_attributes("-topmost", True)
            except tk.TclError:
                pass
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
        self.settings_window.configure(bg=TRANSPARENT_COLOR)
        self.settings_window.overrideredirect(True)
        try:
            self.settings_window.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)
        except tk.TclError:
            pass
        try:
            self.settings_window.wm_attributes("-alpha", layout["alpha"])
        except tk.TclError:
            pass
        self.settings_window.geometry(f"{width}x{height}+{self.root.winfo_x() + layout['offset_x']}+{self.root.winfo_y() + layout['offset_y']}")
        self.settings_window.protocol("WM_DELETE_WINDOW", self.close_settings_window)
        self.settings_window.bind("<Escape>", lambda _e: self.close_settings_window())
        self.settings_window.deiconify()
        self.settings_window.lift()
        try:
            self.settings_window.wm_attributes("-topmost", True)
        except tk.TclError:
            pass
        self.settings_window.grab_set()
        self.settings_window.focus_force()

        self.settings_canvas = tk.Canvas(self.settings_window, width=width, height=height, bg=TRANSPARENT_COLOR, highlightthickness=0, bd=0)
        self.settings_canvas.pack()
        settings_bg = self._load_asset_exact("settings_bg.png", layout["bg_width"], layout["bg_height"])
        if settings_bg is not None:
            self.settings_window_bg = settings_bg
            self.settings_canvas.create_image(layout["bg_x"], layout["bg_y"], image=self.settings_window_bg, anchor="nw")
        if "settings.png" in self.assets:
            settings_icon = self.settings_canvas.create_image(layout["title_icon_x"], layout["title_icon_y"], image=self.assets["settings.png"], anchor="nw")
            self.settings_canvas.tag_bind(settings_icon, "<ButtonPress-1>", self._start_settings_drag)
            self.settings_canvas.tag_bind(settings_icon, "<B1-Motion>", self._drag_settings_window)

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

        self._create_settings_icon_button(
            layout["close_x"],
            layout["close_y"],
            "exit_btn_idle.png",
            "exit_btn_onmouse.png",
            "exit_btn_clicked.png",
            self.close_settings_window,
        )

        title_item = self.settings_canvas.create_text(
            layout["title_x"],
            layout["title_y"],
            anchor="nw",
            text="Application Settings",
            fill="#56f4ee",
            font=("Cascadia Mono", 10, "bold"),
        )
        self.settings_canvas.tag_bind(title_item, "<ButtonPress-1>", self._start_settings_drag)
        self.settings_canvas.tag_bind(title_item, "<B1-Motion>", self._drag_settings_window)

        self.settings_vars["auto_reload_layout"] = tk.BooleanVar(value=self.app_settings["auto_reload_layout"])
        self.settings_vars["discord_rpc_enabled"] = tk.BooleanVar(value=self.app_settings["discord_rpc_enabled"])

        tabs = [
            ("Info", self._render_info_settings_tab),
            ("Discord RPC", self._render_discord_settings_tab),
            ("Editor", self._render_editor_settings_tab),
            ("Preferences", self._render_preferences_settings_tab),
            ("Reset", self._render_reset_settings_tab),
        ]
        for index, (label, callback) in enumerate(tabs):
            tab_y = layout["tabs_y"] + index * layout["tab_step_y"]
            icon_item = self.settings_canvas.create_image(layout["tabs_x"], tab_y + 2, anchor="nw", image=self.assets.get("checkbox_off.png"))
            text_item = self.settings_canvas.create_text(layout["tabs_x"] + 28, tab_y, anchor="nw", text=label, fill="#f0f0f0", font=("Cascadia Mono", 10, "bold"))
            self.settings_tab_items[label] = {"icon": icon_item, "text": text_item, "callback": callback}
            for item_id in (icon_item, text_item):
                self.settings_canvas.tag_bind(item_id, "<Button-1>", lambda _e, name=label: self._select_settings_tab(name))
                self.settings_canvas.tag_bind(item_id, "<Enter>", lambda _e, name=label: self._hover_settings_tab(name, True))
                self.settings_canvas.tag_bind(item_id, "<Leave>", lambda _e, name=label: self._hover_settings_tab(name, False))

        self._select_settings_tab("Info")

    def _create_settings_button(self, x, y, text, command):
        width = 208
        height = 44
        canvas = tk.Canvas(self.settings_window, width=width, height=height, bg=TRANSPARENT_COLOR, highlightthickness=0, bd=0)
        self._set_settings_button_state(canvas, "button_idle.png", text)
        canvas.bind("<Enter>", lambda _e, widget=canvas: self._set_settings_button_state(widget, "button_onmouse.png", text))
        canvas.bind("<Leave>", lambda _e, widget=canvas: self._set_settings_button_state(widget, "button_idle.png", text))
        canvas.bind("<ButtonPress-1>", lambda _e, widget=canvas: self._set_settings_button_state(widget, "button_clicked.png", text))
        canvas.bind("<ButtonRelease-1>", lambda _e, widget=canvas, action=command: (self._set_settings_button_state(widget, "button_onmouse.png", text), action()))
        self.settings_canvas.create_window(x, y, anchor="nw", window=canvas, width=width, height=height)

    def _create_settings_icon_button(self, x, y, idle_name, hover_name, pressed_name, command):
        item = self.settings_canvas.create_image(x, y, anchor="nw", image=self.assets.get(idle_name))
        self.settings_canvas.tag_bind(item, "<Enter>", lambda _e, item_id=item: self.settings_canvas.itemconfigure(item_id, image=self.assets.get(hover_name)))
        self.settings_canvas.tag_bind(item, "<Leave>", lambda _e, item_id=item: self.settings_canvas.itemconfigure(item_id, image=self.assets.get(idle_name)))
        self.settings_canvas.tag_bind(item, "<ButtonPress-1>", lambda _e, item_id=item: self.settings_canvas.itemconfigure(item_id, image=self.assets.get(pressed_name)))
        self.settings_canvas.tag_bind(item, "<ButtonRelease-1>", lambda _e, item_id=item: self.settings_canvas.itemconfigure(item_id, image=self.assets.get(hover_name)))
        self.settings_canvas.tag_bind(item, "<Button-1>", lambda _e: command())

    def _set_settings_button_state(self, canvas, image_name, text):
        canvas.delete("all")
        if image_name in self.assets:
            canvas.create_image(0, 0, image=self.assets[image_name], anchor="nw")
        canvas.create_text(104, 22, text=text, fill="#f0f0f0", font=("Segoe UI", 9, "bold"))

    def _clear_settings_content(self):
        if self.settings_canvas is None:
            return
        for widget in self.settings_action_widgets:
            try:
                widget.destroy()
            except tk.TclError:
                pass
        self.settings_action_widgets.clear()
        for item in self.settings_content_items:
            self.settings_canvas.delete(item)
        self.settings_content_items.clear()

    def _start_settings_drag(self, event):
        self.settings_drag_offset_x = event.x_root - self.settings_window.winfo_x()
        self.settings_drag_offset_y = event.y_root - self.settings_window.winfo_y()

    def _drag_settings_window(self, event):
        x = event.x_root - self.settings_drag_offset_x
        y = event.y_root - self.settings_drag_offset_y
        self.settings_window.geometry(f"+{x}+{y}")

    def _hover_settings_tab(self, name, hovered):
        if not self.settings_canvas or name not in self.settings_tab_items:
            return
        if getattr(self, "active_settings_tab", None) == name:
            self.settings_canvas.itemconfigure(self.settings_tab_items[name]["icon"], image=self.assets.get("checkbox_on.png"))
            return
        self.settings_canvas.itemconfigure(
            self.settings_tab_items[name]["icon"],
            image=self.assets.get("checkbox_onmouse.png" if hovered else "checkbox_off.png"),
        )

    def _select_settings_tab(self, name):
        self.active_settings_tab = name
        for tab_name, items in self.settings_tab_items.items():
            self.settings_canvas.itemconfigure(
                items["icon"],
                image=self.assets.get("checkbox_on.png" if tab_name == name else "checkbox_off.png"),
            )
        self._clear_settings_content()
        self.settings_tab_items[name]["callback"]()

    def _content_anchor(self, rel_x=0, rel_y=0):
        layout = self.layout["settings_window"]
        return layout["content_x"] + rel_x, layout["content_y"] + rel_y

    def _render_text_block(self, lines, rel_x, rel_y, font=("Cascadia Mono", 9, "bold"), fill="#f0f0f0", anchor="nw", justify="left"):
        x, y = self._content_anchor(rel_x, rel_y)
        item = self.settings_canvas.create_text(x, y, text="\n".join(lines), anchor=anchor, fill=fill, font=font, justify=justify)
        self.settings_content_items.append(item)
        return item

    def _render_info_settings_tab(self):
        self._render_text_block(
            [
                "SGMEditor is a IDE for creating, editing,",
                "and building modifications for Ren'Py-based games",
                "by Soviet Games.",
            ],
            12,
            34,
        )
        if "lunar_avatar.png" in self.assets:
            x, y = self._content_anchor(0, 152)
            item = self.settings_canvas.create_image(x, y, image=self.assets["lunar_avatar.png"], anchor="nw")
            self.settings_content_items.append(item)
        self._render_text_block(
            [
                "Code, Graphical UI Design,",
                "Realisation by Lunar.",
                "Idea by authors of LMR SE",
            ],
            128,
            188,
        )
        if "py_logo.png" in self.assets:
            x, y = self._content_anchor(0, 440)
            self.settings_content_items.append(self.settings_canvas.create_image(x, y, image=self.assets["py_logo.png"], anchor="nw"))
        if "sg_logo.png" in self.assets:
            x, y = self._content_anchor(220, 426)
            self.settings_content_items.append(self.settings_canvas.create_image(x, y, image=self.assets["sg_logo.png"], anchor="nw"))
        self._render_text_block(["SGME Build 15391"], 118, 444, font=("Cascadia Mono", 14, "bold"))
        self._render_text_block(
            [
                "Written on Python Libraries",
                "Supported games:",
                "ES, LMR, ES:2(Later)",
            ],
            108,
            474,
            font=("Cascadia Mono", 8, "bold"),
        )

    def _render_discord_settings_tab(self):
        self._render_checkbox_row(0, 24, self.settings_vars["discord_rpc_enabled"], "Enable Discord RPC")
        self._render_action_button("open_rpc_config", "Open RPC Config", 0, 72, lambda: self._open_path_in_system(DISCORD_RPC_PATH / "config.json"))

    def _render_editor_settings_tab(self):
        self._render_checkbox_row(0, 24, self.settings_vars["auto_reload_layout"], "Auto reload layout JSON")
        self._render_action_button("open_layout_json", "Open Layout JSON", 0, 72, lambda: self._open_path_in_system(LAYOUT_PATH))
        self._render_action_button("reload_layout", "Reload Layout", 0, 112, self._reload_layout)

    def _render_preferences_settings_tab(self):
        self._render_action_button("open_app_settings", "Open App Settings", 0, 24, lambda: self._open_path_in_system(APP_SETTINGS_PATH))
        self._render_action_button("save_settings", "Save Settings", 0, 64, self._save_settings)

    def _render_reset_settings_tab(self):
        self._render_action_button("reset_layout", "Reset Layout To Defaults", 0, 24, self._reset_layout_to_defaults)
        self._render_action_button("reset_app_settings", "Reset App Settings", 0, 64, self._reset_app_settings)

    def _render_checkbox_row(self, rel_x, rel_y, variable, label):
        x, y = self._content_anchor(rel_x, rel_y)
        icon_name = "checkbox_on.png" if variable.get() else "checkbox_off.png"
        icon_item = self.settings_canvas.create_image(x, y, image=self.assets.get(icon_name), anchor="nw")
        text_item = self.settings_canvas.create_text(x + 28, y + 1, text=label, anchor="nw", fill="#f0f0f0", font=("Cascadia Mono", 9, "bold"))
        self.settings_content_items.extend([icon_item, text_item])

        def toggle(_event=None):
            variable.set(not bool(variable.get()))
            self.settings_canvas.itemconfigure(icon_item, image=self.assets.get("checkbox_on.png" if variable.get() else "checkbox_off.png"))

        for item in (icon_item, text_item):
            self.settings_canvas.tag_bind(item, "<Button-1>", toggle)
            self.settings_canvas.tag_bind(item, "<Enter>", lambda _e: self.settings_canvas.itemconfigure(icon_item, image=self.assets.get("checkbox_onmouse.png")))
            self.settings_canvas.tag_bind(item, "<Leave>", lambda _e: self.settings_canvas.itemconfigure(icon_item, image=self.assets.get("checkbox_on.png" if variable.get() else "checkbox_off.png")))

    def _render_action_button(self, button_id, label, rel_x, rel_y, action):
        x, y = self._content_anchor(rel_x, rel_y)
        button_cfg = self.layout["settings_window"]["action_buttons"].get(button_id, {"width": 100, "height": 22, "alpha": 1.0})
        middle_width = int(button_cfg.get("width", 100))
        button_height = int(button_cfg.get("height", 22))
        button_alpha = float(button_cfg.get("alpha", 1.0))
        left_idle = self.assets.get("button_border_left_idle.png")
        right_idle = self.assets.get("button_border_right_idle.png")
        if left_idle is None or right_idle is None:
            return

        left_width = max(1, int(round(left_idle.width() * (button_height / max(1, left_idle.height())))))
        right_width = max(1, int(round(right_idle.width() * (button_height / max(1, right_idle.height())))))
        height = max(1, button_height)
        total_width = left_width + middle_width + right_width
        widget = tk.Canvas(self.settings_window, width=total_width, height=height, bg=TRANSPARENT_COLOR, highlightthickness=0, bd=0)
        widget._state_images = {}  # type: ignore[attr-defined]

        def build_state(state_name: str):
            left = self._load_asset_exact_alpha(f"button_border_left_{state_name}.png", left_width, height, button_alpha)
            middle = self._load_asset_exact_alpha(f"button_middle_{state_name}.png", middle_width, height, button_alpha)
            right = self._load_asset_exact_alpha(f"button_border_right_{state_name}.png", right_width, height, button_alpha)
            if left is None or middle is None or right is None:
                return
            widget._state_images[state_name] = (left, middle, right)  # type: ignore[attr-defined]

        for state in ("idle", "onmouse", "clicked"):
            build_state(state)

        def draw_state(state_name: str):
            state_images = widget._state_images.get(state_name)  # type: ignore[attr-defined]
            if state_images is None:
                return
            left, middle, right = state_images
            widget.delete("all")
            widget.create_image(0, 0, image=left, anchor="nw")
            widget.create_image(left_width, 0, image=middle, anchor="nw")
            widget.create_image(left_width + middle_width, 0, image=right, anchor="nw")
            widget.create_text(total_width // 2, height // 2, text=label, fill="#000000", font=("Cascadia Mono", 9, "bold"))

        draw_state("idle")
        widget.bind("<Enter>", lambda _e: draw_state("onmouse"))
        widget.bind("<Leave>", lambda _e: draw_state("idle"))
        widget.bind("<ButtonPress-1>", lambda _e: draw_state("clicked"))
        widget.bind("<ButtonRelease-1>", lambda _e: (draw_state("onmouse"), action()))
        self.settings_action_widgets.append(widget)
        window_item = self.settings_canvas.create_window(x, y, anchor="nw", window=widget, width=total_width, height=height)
        self.settings_content_items.append(window_item)

    def _render_info_settings_tab(self):
        layout = self.layout["settings_window"]
        texts = layout["texts"]
        logos = layout["logos"]

        top_item = self.settings_canvas.create_text(
            texts["top_x"],
            texts["top_y"],
            text="\n".join(
                [
                    "SGMEditor is a IDE for creating, editing,",
                    "and building modifications for Ren'Py-based games",
                    "by Soviet Games.",
                ]
            ),
            anchor="n",
            fill="#f0f0f0",
            font=("Cascadia Mono", 9, "bold"),
            justify="center",
        )
        self.settings_content_items.append(top_item)

        if "lunar_avatar.png" in self.assets:
            self.settings_content_items.append(
                self.settings_canvas.create_image(logos["lunar_x"], logos["lunar_y"], image=self.assets["lunar_avatar.png"], anchor="nw")
            )

        middle_item = self.settings_canvas.create_text(
            texts["middle_x"],
            texts["middle_y"],
            text="\n".join(
                [
                    "Code, Graphical UI Design,",
                    "Realisation by Lunar.",
                    "Idea by authors of LMR SE",
                ]
            ),
            anchor="n",
            fill="#f0f0f0",
            font=("Cascadia Mono", 9, "bold"),
            justify="center",
        )
        self.settings_content_items.append(middle_item)

        if "py_logo.png" in self.assets:
            self.settings_content_items.append(
                self.settings_canvas.create_image(logos["python_x"], logos["python_y"], image=self.assets["py_logo.png"], anchor="nw")
            )
        if "sg_logo.png" in self.assets:
            soviet_games_logo = self._load_asset_exact("sg_logo.png", logos["soviet_games_width"], logos["soviet_games_height"])
            self.settings_content_items.append(
                self.settings_canvas.create_image(
                    logos["soviet_games_x"],
                    logos["soviet_games_y"],
                    image=soviet_games_logo if soviet_games_logo is not None else self.assets["sg_logo.png"],
                    anchor="nw",
                )
            )
            self.settings_soviet_games_logo = soviet_games_logo

        discord_info_item = self.settings_canvas.create_text(
            texts["discord_x"],
            texts["discord_y"],
            text="Developed for Alzheimer Team",
            anchor="n",
            fill="#f0f0f0",
            font=("Cascadia Mono", 9, "bold"),
            justify="center",
        )
        self.settings_content_items.append(discord_info_item)

        discord_link_item = self.settings_canvas.create_text(
            texts["discord_x"],
            texts["discord_y"] + 18,
            text="Discord Link: https://discord.gg/dd2drP5PnP",
            anchor="n",
            fill="#56f4ee",
            font=("Cascadia Mono", 9, "bold"),
            justify="center",
        )
        self.settings_content_items.append(discord_link_item)
        self.settings_canvas.tag_bind(discord_link_item, "<Button-1>", lambda _e: webbrowser.open("https://discord.gg/dd2drP5PnP"))
        self.settings_canvas.tag_bind(discord_link_item, "<Enter>", lambda _e, item_id=discord_link_item: self.settings_canvas.itemconfigure(item_id, fill="#ffffff"))
        self.settings_canvas.tag_bind(discord_link_item, "<Leave>", lambda _e, item_id=discord_link_item: self.settings_canvas.itemconfigure(item_id, fill="#56f4ee"))

        bottom_item = self.settings_canvas.create_text(
            texts["bottom_x"],
            texts["bottom_y"],
            text="\n".join(
                [
                    "SGME Build 15391",
                    "Written on Python Libraries",
                    "Supported games:",
                    "ES, LMR, ES:2(Later)",
                ]
            ),
            anchor="n",
            fill="#f0f0f0",
            font=("Cascadia Mono", 8, "bold"),
            justify="center",
        )
        self.settings_content_items.append(bottom_item)

    def _reset_layout_to_defaults(self):
        LAYOUT_PATH.write_text(json.dumps(DEFAULT_LAYOUT, indent=2), encoding="utf-8")

    def _reset_app_settings(self):
        self.app_settings = load_app_settings()
        self.settings_vars["auto_reload_layout"].set(self.app_settings["auto_reload_layout"])
        self.settings_vars["discord_rpc_enabled"].set(self.app_settings["discord_rpc_enabled"])
        APP_SETTINGS_PATH.write_text(json.dumps(self.app_settings, indent=2), encoding="utf-8")

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
            try:
                self.settings_window.grab_release()
            except tk.TclError:
                pass
            self.settings_window.destroy()
        self.settings_window = None
        self.settings_canvas = None
        self.settings_window_bg = None
        self.settings_soviet_games_logo = None

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

        file_tabs = layout.get("file_tabs", DEFAULT_LAYOUT["file_tabs"])
        layout["file_tabs"] = {
            "x": max(0, min(int(file_tabs.get("x", DEFAULT_LAYOUT["file_tabs"]["x"])), width - 20)),
            "y": max(0, min(int(file_tabs.get("y", DEFAULT_LAYOUT["file_tabs"]["y"])), height - 20)),
            "gap": max(0, int(file_tabs.get("gap", DEFAULT_LAYOUT["file_tabs"]["gap"]))),
            "height": max(10, int(file_tabs.get("height", DEFAULT_LAYOUT["file_tabs"]["height"]))),
            "middle_min_width": max(20, int(file_tabs.get("middle_min_width", DEFAULT_LAYOUT["file_tabs"]["middle_min_width"]))),
            "text_padding_x": max(0, int(file_tabs.get("text_padding_x", DEFAULT_LAYOUT["file_tabs"]["text_padding_x"]))),
            "active_text_color": str(file_tabs.get("active_text_color", DEFAULT_LAYOUT["file_tabs"]["active_text_color"])),
            "inactive_text_color": str(file_tabs.get("inactive_text_color", DEFAULT_LAYOUT["file_tabs"]["inactive_text_color"])),
            "close_padding_right": max(0, int(file_tabs.get("close_padding_right", DEFAULT_LAYOUT["file_tabs"]["close_padding_right"]))),
            "close_color_active": str(file_tabs.get("close_color_active", DEFAULT_LAYOUT["file_tabs"]["close_color_active"])),
            "close_color_inactive": str(file_tabs.get("close_color_inactive", DEFAULT_LAYOUT["file_tabs"]["close_color_inactive"])),
        }

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
        settings["alpha"] = max(0.1, min(float(settings.get("alpha", default_settings["alpha"])), 1.0))
        settings["offset_x"] = int(settings.get("offset_x", default_settings["offset_x"]))
        settings["offset_y"] = int(settings.get("offset_y", default_settings["offset_y"]))
        settings["bg_x"] = int(settings.get("bg_x", default_settings["bg_x"]))
        settings["bg_y"] = int(settings.get("bg_y", default_settings["bg_y"]))
        settings["close_x"] = int(settings.get("close_x", default_settings["close_x"]))
        settings["close_y"] = int(settings.get("close_y", default_settings["close_y"]))
        for key in ("title_icon_x", "title_icon_y", "title_x", "title_y", "tabs_x", "tabs_y", "content_x", "content_y", "button_left_x", "button_right_x", "button_y"):
            settings[key] = int(settings.get(key, default_settings[key]))
        for key in ("bg_width", "bg_height", "tabs_width", "tabs_height", "tab_step_y", "content_width", "content_height"):
            settings[key] = max(10, int(settings.get(key, default_settings[key])))
        if not isinstance(settings.get("texts"), dict):
            settings["texts"] = {}
        for key, default_value in default_settings["texts"].items():
            settings["texts"][key] = int(settings["texts"].get(key, default_value))
        if not isinstance(settings.get("action_buttons"), dict):
            settings["action_buttons"] = {}
        for key, default_value in default_settings["action_buttons"].items():
            raw_value = settings["action_buttons"].get(key, default_value)
            if isinstance(raw_value, (int, float)):
                raw_value = {"width": raw_value, "height": default_value["height"], "alpha": default_value["alpha"]}
            elif not isinstance(raw_value, dict):
                raw_value = default_value
            settings["action_buttons"][key] = {
                "width": max(10, int(raw_value.get("width", default_value["width"]))),
                "height": max(1, int(raw_value.get("height", default_value["height"]))),
                "alpha": max(0.0, min(float(raw_value.get("alpha", default_value["alpha"])), 1.0)),
            }
        if not isinstance(settings.get("logos"), dict):
            settings["logos"] = {}
        for key, default_value in default_settings["logos"].items():
            value = int(settings["logos"].get(key, default_value))
            if key in {"soviet_games_width", "soviet_games_height"}:
                value = max(1, value)
            settings["logos"][key] = value

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
        current_file_before = self.current_file
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
        reopen_settings = self.settings_window is not None and self.settings_window.winfo_exists()
        if reopen_settings:
            self.close_settings_window()
            self.root.after(20, self.open_settings_window)

        if self.project_dir is not None:
            self._reload_project_files()
            if selected_path is not None and self.file_tree is not None:
                for item_id, path in self.tree_item_paths.items():
                    if path == selected_path:
                        self.file_tree.selection_set(item_id)
                        self.file_tree.focus(item_id)
                        break

        if current_file_before is not None and self.editor_text is not None:
            self.file_buffers[current_file_before] = editor_content
        if self.current_file is not None and self.editor_text is not None:
            self.editor_text.delete("1.0", "end")
            self.editor_text.insert("1.0", self.file_buffers.get(self.current_file, editor_content))
            self.editor_text.mark_set("insert", cursor_index)
            self.editor_text.see(cursor_index)
        self._update_status()
        self._request_render_file_tabs()

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
        self.open_files.clear()
        self.file_buffers.clear()
        self.dirty_files.clear()
        self.current_file = None
        self._reload_project_files()
        self._update_status()
        self._update_presence()
        self._request_render_file_tabs()

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
        if self.current_file is not None and self.editor_text is not None:
            self.file_buffers[self.current_file] = self.editor_text.get("1.0", "end-1c")
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = path.read_text(encoding="utf-8", errors="replace")
        if path not in self.open_files:
            self.open_files.append(path)
        self.current_file = path
        content = self.file_buffers.get(path, content)
        self.file_buffers[path] = content
        self.dirty_files.discard(path)
        self.editor_text.delete("1.0", "end")
        self.editor_text.insert("1.0", content)
        self.editor_text.focus_set()
        self._refresh_line_numbers()
        self._update_status(refresh_lines=False)
        self._update_presence()
        self._request_render_file_tabs()

    def switch_to_file(self, path: Path):
        if path == self.current_file:
            return
        self.open_file(path)

    def close_file_tab(self, path: Path):
        if path not in self.open_files:
            return
        was_current = path == self.current_file
        current_index = self.open_files.index(path)
        self.open_files.remove(path)
        self.file_buffers.pop(path, None)
        self.dirty_files.discard(path)
        if not self.open_files:
            self.current_file = None
            if self.editor_text is not None:
                self.editor_text.delete("1.0", "end")
                self.editor_text.focus_set()
            self.last_line_count = 0
            self._refresh_line_numbers(force=True)
            self._update_status(refresh_lines=False)
            self._update_presence()
            self._request_render_file_tabs()
            return
        if was_current:
            next_index = max(0, min(current_index, len(self.open_files) - 1))
            self.open_file(self.open_files[next_index])
        else:
            self._request_render_file_tabs()

    def save_current_file(self):
        if self.current_file is None:
            return
        content = self.editor_text.get("1.0", "end-1c")
        self.file_buffers[self.current_file] = content
        self.current_file.write_text(content, encoding="utf-8")
        self.dirty_files.discard(self.current_file)
        self._update_status()
        self._request_render_file_tabs()

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

    def _refresh_line_numbers(self, force=False):
        line_count = int(self.editor_text.index("end-1c").split(".")[0])
        if not force and line_count == self.last_line_count:
            return
        self.last_line_count = line_count
        data = "\n".join(str(number) for number in range(1, line_count + 1))
        self.line_numbers.config(state="normal")
        self.line_numbers.delete("1.0", "end")
        self.line_numbers.insert("1.0", data)
        self.line_numbers.config(state="disabled")

    def _update_status(self, refresh_lines=True):
        project_name = self.project_dir.name if self.project_dir else "No project open"
        current_name = self.current_file.name if self.current_file else "No file open"
        line, column = self.editor_text.index("insert").split(".")
        self.canvas.itemconfigure(self.mode_id, text=f"Mode: {project_name}")
        self.canvas.itemconfigure(self.cursor_id, text=f"{current_name}   String: {line}   Column: {column}")
        if refresh_lines:
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
