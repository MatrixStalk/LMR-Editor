import json
import os
import queue
import re
import shutil
import struct
import threading
import time
import tkinter as tk
import webbrowser
import sys
import tempfile
import ctypes
import winsound
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

try:
    import UnityPy
except ImportError:
    UnityPy = None

try:
    from pypresence import Presence
except ImportError:
    Presence = None


BASE_DIR = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
ASSETS_DIR = BASE_DIR / "assets"
DISCORD_RPC_PATH = BASE_DIR / "discordrpc"
LAYOUT_PATH = BASE_DIR / "editor_layout.json"
APP_SETTINGS_PATH = BASE_DIR / "app_settings.json"
LMR_GAME_DATA_DIR = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Love, Money, Rock-n-Roll\Love, Money, Rock'n'Roll_Data")
LMR_RESOURCES_ASSETS_PATH = LMR_GAME_DATA_DIR / "resources.assets"
LMR_RESOURCES_RESS_PATH = LMR_GAME_DATA_DIR / "resources.assets.resS"
LMR_BUNDLES_DIR = LMR_GAME_DATA_DIR / "StreamingAssets" / "aa" / "StandaloneWindows64"
LMR_FALLBACK_UNITY_VERSION = "6000.0.59f2"

BACKGROUND_IMAGE_PATH = ASSETS_DIR / "mb_bg.png"
TRANSPARENT_COLOR = "#010203"
PANEL_BACKGROUND = "#090909"
PANEL_LINES_BACKGROUND = "#101010"
TEXT_EXTENSIONS = {".json", ".md", ".py", ".rpy", ".rpym", ".toml", ".txt", ".xml", ".yml", ".yaml"}
SUPPORTED_MOD_GAMES = [
    {"id": "lmr", "name": "Love, Money, Rock'n'Roll"},
    {"id": "es", "name": "Everlasting Summer"},
    {"id": "es2", "name": "Everlasting Summer 2"},
]


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
        "default_lmr_game_dir": "",
        "default_es_game_dir": "",
    }
    settings = load_json(APP_SETTINGS_PATH, default_settings)
    merged = default_settings.copy()
    for key, value in settings.items():
        if isinstance(value, bool):
            merged[key] = value
        elif key in {"default_lmr_game_dir", "default_es_game_dir"} and isinstance(value, str):
            merged[key] = value
    return merged


def generate_build_number() -> str:
    if getattr(sys, "frozen", False):
        source_path = Path(sys.executable)
    else:
        source_path = Path(__file__).resolve()

    try:
        modified_at = time.localtime(source_path.stat().st_mtime)
    except OSError:
        modified_at = time.localtime()

    timestamp_formula = (
        modified_at.tm_year * 100000000
        + modified_at.tm_mon * 1000000
        + modified_at.tm_mday * 10000
        + modified_at.tm_hour * 100
        + modified_at.tm_min
    )
    pseudo_random = (
        timestamp_formula * 73
        + modified_at.tm_sec * 197
        + modified_at.tm_yday * 19
    ) % 90000
    return f"{pseudo_random + 10000:05d}"


DEFAULT_LAYOUT = {
    "window": {"width": 1919, "height": 1079, "drag_top_height": 52},
    "drag_area": {"x": 94, "y": 22, "width": 1720, "height": 92},
    "menu": {"project_x": 148, "file_x": 203, "settings_x": 239, "resource_manager_x": 298, "y": 31},
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
    "editor_scrollbar": {"x": 1557, "y": 101, "width": 14, "height": 823},
    "editor_h_scrollbar": {"x": 180, "y": 928, "width": 1374, "height": 14},
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
    },
    "create_project_window": {
        "width": 840,
        "height": 760,
        "title_x": 420,
        "title_y": 24,
        "game_label_x": 30,
        "game_label_y": 58,
        "game_x": 30,
        "game_y": 82,
        "game_step_y": 26,
        "menu_label_x": 30,
        "menu_label_y": 196,
        "menu_x": 30,
        "menu_y": 220,
        "menu_step_y": 28,
        "game_item_width": 300,
        "menu_item_width": 170,
        "content_x": 194,
        "content_y": 286,
        "content_width": 614,
        "content_height": 408,
        "actions_y": 716,
        "return_x": 540,
        "create_x": 680,
        "general": {
            "game_folder_label_x": 18,
            "game_folder_label_y": 18,
            "game_folder_entry_x": 18,
            "game_folder_entry_y": 44,
            "game_folder_entry_width": 430,
            "browse_x": 462,
            "browse_y": 44,
            "browse_width": 72,
            "project_id_label_x": 18,
            "project_id_label_y": 90,
            "project_id_entry_x": 18,
            "project_id_entry_y": 116,
            "project_id_entry_width": 220,
            "project_id_hint_x": 258,
            "project_id_hint_y": 120,
            "target_label_x": 18,
            "target_label_y": 164,
            "target_value_x": 18,
            "target_value_y": 190,
            "target_value_width": 560,
            "target_value_height": 88,
            "note_x": 18,
            "note_y": 292
        },
        "lmr": {
            "title_label_x": 18,
            "title_label_y": 18,
            "title_entry_x": 18,
            "title_entry_y": 44,
            "title_entry_width": 270,
            "version_label_x": 308,
            "version_label_y": 18,
            "version_entry_x": 308,
            "version_entry_y": 44,
            "version_entry_width": 120,
            "description_label_x": 18,
            "description_label_y": 82,
            "description_x": 18,
            "description_y": 106,
            "description_width": 410,
            "description_height": 60,
            "cover_label_x": 448,
            "cover_label_y": 18,
            "cover_entry_x": 448,
            "cover_entry_y": 44,
            "cover_entry_width": 130,
            "cover_warning_label_x": 448,
            "cover_warning_label_y": 82,
            "cover_warning_1_x": 448,
            "cover_warning_1_y": 106,
            "cover_warning_2_x": 448,
            "cover_warning_2_y": 124,
            "cover_button_x": 448,
            "cover_button_y": 152,
            "cover_button_width": 72,
            "resources_label_x": 18,
            "resources_label_y": 186,
            "resources_note_x": 18,
            "resources_note_y": 210,
            "resources_x": 18,
            "resources_y": 236,
            "resources_column_width": 192,
            "resources_row_height": 24
        },
        "es": {
            "display_label_x": 18,
            "display_label_y": 18,
            "display_entry_x": 18,
            "display_entry_y": 44,
            "display_entry_width": 320,
            "note_1_x": 18,
            "note_1_y": 82,
            "note_2_x": 18,
            "note_2_y": 124
        }
    },
    "create_file_window": {
        "width": 520,
        "height_lmr": 350,
        "height_es": 250,
        "title_x": 260,
        "title_y": 20,
        "type_x": 28,
        "type_y": 56,
        "type_step_y": 26,
        "type_item_width_lmr": 260,
        "type_item_width_es": 220,
        "file_name_label_x": 28,
        "file_name_label_y_lmr": 176,
        "file_name_label_y_es": 120,
        "file_name_entry_x": 28,
        "file_name_entry_y_lmr": 200,
        "file_name_entry_y_es": 144,
        "file_name_entry_width": 300,
        "technical_label_x": 28,
        "technical_label_y": 236,
        "technical_entry_x": 28,
        "technical_entry_y": 260,
        "technical_entry_width": 180,
        "folder_label_x": 250,
        "folder_label_y": 236,
        "folder_entry_x": 250,
        "folder_entry_y": 260,
        "folder_entry_width": 180,
        "folder_note_x": 28,
        "folder_note_y": 290,
        "return_x": 270,
        "create_x": 390,
        "actions_y_lmr": 306,
        "actions_y_es": 206
    }
}


RPC_CONFIG = load_discord_rpc_config()
APP_DISPLAY_NAME = RPC_CONFIG["app_display_name"]
APP_SETTINGS = load_app_settings()
APP_BUILD_NUMBER = generate_build_number()


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
        self.saved_file_snapshots: dict[Path, str] = {}
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
        self.editor_scrollbar = None
        self.editor_scroll_spacer = None
        self.editor_scrollbar_images = {}
        self.editor_scrollbar_thumb = None
        self.editor_scrollbar_thumb_offset_y = 0
        self.editor_scrollbar_view = (0.0, 1.0)
        self.editor_scrollbar_hovered = False
        self.editor_scrollbar_pressed = False
        self.editor_h_scrollbar = None
        self.editor_h_scrollbar_images = {}
        self.editor_h_scrollbar_thumb = None
        self.editor_h_scrollbar_thumb_offset_x = 0
        self.editor_h_scrollbar_view = (0.0, 1.0)
        self.editor_h_scrollbar_hovered = False
        self.editor_h_scrollbar_pressed = False
        self.header_id = None
        self.mode_id = None
        self.cursor_id = None
        self.drag_zone_id = None
        self.popup_menus: dict[str, tk.Menu] = {}
        self.editor_context_menu = None
        self.top_menu_item_ids = []
        self.tree_item_paths: dict[str, Path] = {}
        self.settings_window = None
        self.confirm_window = None
        self.asset_viewer_window = None
        self.asset_viewer_tree = None
        self.asset_viewer_entries = []
        self.asset_viewer_filtered_entries = []
        self.asset_viewer_bundle_paths = []
        self.asset_viewer_bundle_var = None
        self.asset_viewer_search_var = None
        self.asset_viewer_type_var = None
        self.asset_viewer_preview_label = None
        self.asset_viewer_preview_image = None
        self.asset_viewer_audio_info_var = None
        self.asset_viewer_audio_temp_path = None
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
        self.file_tab_item_ids = []
        self.file_tab_tags = []
        self.file_tab_render_job = None
        self.hovered_tree_item = None
        self.last_line_count = 0
        self.line_numbers_refresh_job = None

        self._build_window()
        self._build_popup_menus()
        self._bind_shortcuts()
        self._update_status()
        self._update_presence()
        self._presence_loop()
        self._watch_layout_file()
        self._schedule_line_numbers_refresh()

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
            "list_m.png",
            "list_track_b.png",
            "list_track_m.png",
            "list_track_t.png",
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
            "window_b.png",
            "window_back.png",
            "window_l.png",
            "window_lb.png",
            "window_lt.png",
            "window_r.png",
            "window_rb.png",
            "window_rt.png",
            "window_t.png",
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
        cache_key = ("exact", name, width, height)
        cached = self.resized_asset_cache.get(cache_key)
        if cached is not None:
            return cached

        if Image is not None and ImageTk is not None:
            with Image.open(path) as source:
                resized = source.convert("RGBA").resize((width, height), Image.Resampling.LANCZOS)
                image = ImageTk.PhotoImage(resized)
                self.resized_asset_cache[cache_key] = image
                return image

        image = self._resize_image_exact(tk.PhotoImage(file=str(path)), width, height)
        self.resized_asset_cache[cache_key] = image
        return image

    def _load_asset_exact_alpha(self, name: str, width: int, height: int, alpha: float):
        path = ASSETS_DIR / name
        if not path.exists():
            return None

        width = max(1, int(width))
        height = max(1, int(height))
        alpha = max(0.0, min(float(alpha), 1.0))
        cache_key = ("alpha", name, width, height, round(alpha, 4))
        cached = self.resized_asset_cache.get(cache_key)
        if cached is not None:
            return cached

        if Image is not None and ImageTk is not None:
            with Image.open(path) as source:
                resized = source.convert("RGBA").resize((width, height), Image.Resampling.LANCZOS)
                if alpha < 1.0:
                    r, g, b, a = resized.split()
                    a = a.point(lambda value: int(value * alpha))
                    resized = Image.merge("RGBA", (r, g, b, a))
                image = ImageTk.PhotoImage(resized)
                self.resized_asset_cache[cache_key] = image
                return image

        image = self._load_asset_exact(name, width, height)
        self.resized_asset_cache[cache_key] = image
        return image

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

        self._render_top_menu_buttons()

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
        editor_font = ("Cascadia Mono", 10)
        self.editor_text = tk.Text(
            self.root,
            bg=PANEL_BACKGROUND,
            fg="#d8d8d8",
            insertbackground="#56f4ee",
            selectbackground="#143c3d",
            selectforeground="#ffffff",
            font=editor_font,
            bd=0,
            highlightthickness=0,
            relief="flat",
            wrap="none",
            undo=True,
            autoseparators=True,
            maxundo=-1,
            padx=0,
            pady=0,
            spacing1=0,
            spacing2=0,
            spacing3=0,
            yscrollcommand=self._sync_editor_vertical_views,
            xscrollcommand=self._sync_editor_horizontal_views,
        )
        self.editor_text.bind("<Button-1>", self._focus_editor_widget)
        self.editor_text.bind("<Tab>", self._insert_editor_spaces)
        self.editor_text.bind("<KeyPress>", self._handle_shortcut_keypress)
        self.editor_text.bind("<KeyRelease>", self._handle_editor_key_release)
        self.editor_text.bind("<ButtonRelease>", lambda _e: self._update_status(refresh_lines=False))
        self.editor_text.bind("<Button-3>", self._show_editor_context_menu)
        self._configure_editor_syntax_tags()
        self.canvas.create_window(editor["x"], editor["y"], anchor="nw", window=self.editor_text, width=editor["width"], height=editor["height"])

        line_numbers = self.layout["line_numbers"]
        self.line_numbers = tk.Canvas(
            self.root,
            bg=PANEL_LINES_BACKGROUND,
            bd=0,
            highlightthickness=0,
            relief="flat",
            takefocus=0,
            width=line_numbers["width"],
            height=line_numbers["height"],
        )
        self.line_numbers.bind("<MouseWheel>", self._scroll_editor_from_line_numbers)
        self.line_numbers.bind("<Button-4>", self._scroll_editor_from_line_numbers)
        self.line_numbers.bind("<Button-5>", self._scroll_editor_from_line_numbers)
        self.canvas.create_window(
            line_numbers["x"],
            line_numbers["y"],
            anchor="nw",
            window=self.line_numbers,
            width=line_numbers["width"],
            height=line_numbers["height"],
        )

        scrollbar = self.layout["editor_scrollbar"]
        self.editor_scrollbar = tk.Canvas(
            self.root,
            bg=PANEL_BACKGROUND,
            bd=0,
            highlightthickness=0,
            relief="flat",
            width=scrollbar["width"],
            height=scrollbar["height"],
        )
        self.editor_scrollbar.bind("<Button-1>", self._handle_editor_scrollbar_press)
        self.editor_scrollbar.bind("<B1-Motion>", self._handle_editor_scrollbar_drag)
        self.editor_scrollbar.bind("<ButtonRelease-1>", self._handle_editor_scrollbar_release)
        self.editor_scrollbar.bind("<Motion>", self._handle_editor_scrollbar_motion)
        self.editor_scrollbar.bind("<Leave>", self._handle_editor_scrollbar_leave)
        self.editor_scrollbar.bind("<MouseWheel>", self._scroll_editor_from_line_numbers)
        self.editor_scrollbar.bind("<Button-4>", self._scroll_editor_from_line_numbers)
        self.editor_scrollbar.bind("<Button-5>", self._scroll_editor_from_line_numbers)
        self.canvas.create_window(
            scrollbar["x"],
            scrollbar["y"],
            anchor="nw",
            window=self.editor_scrollbar,
            width=scrollbar["width"],
            height=scrollbar["height"],
        )
        self._render_editor_scrollbar(0.0, 1.0)

        h_scrollbar = self.layout["editor_h_scrollbar"]
        self.editor_h_scrollbar = tk.Canvas(
            self.root,
            bg=PANEL_BACKGROUND,
            bd=0,
            highlightthickness=0,
            relief="flat",
            width=h_scrollbar["width"],
            height=h_scrollbar["height"],
        )
        self.editor_h_scrollbar.bind("<Button-1>", self._handle_editor_h_scrollbar_press)
        self.editor_h_scrollbar.bind("<B1-Motion>", self._handle_editor_h_scrollbar_drag)
        self.editor_h_scrollbar.bind("<ButtonRelease-1>", self._handle_editor_h_scrollbar_release)
        self.editor_h_scrollbar.bind("<Motion>", self._handle_editor_h_scrollbar_motion)
        self.editor_h_scrollbar.bind("<Leave>", self._handle_editor_h_scrollbar_leave)
        self.canvas.create_window(
            h_scrollbar["x"],
            h_scrollbar["y"],
            anchor="nw",
            window=self.editor_h_scrollbar,
            width=h_scrollbar["width"],
            height=h_scrollbar["height"],
        )
        self._render_editor_h_scrollbar(0.0, 1.0)

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
        project_menu.add_command(label="Create Project", command=self.create_mod_project)
        project_menu.add_command(label="Create Project File", command=self.create_project_text_file)
        project_menu.add_command(label="LMR Bundle Extractor", command=self.open_lmr_bundle_extractor)
        project_menu.add_separator()
        project_menu.add_command(label="Open Project", command=self.open_project)
        project_menu.add_command(label="Reload Files", command=self._reload_project_files)
        self.popup_menus["Project"] = project_menu

        file_menu = tk.Menu(self.root, tearoff=False, bg="#111111", fg="#d8d8d8", activebackground="#143c3d", activeforeground="#56f4ee", bd=0)
        file_menu.add_command(label="Save", command=self.save_current_file)
        file_menu.add_command(label="Export ZIP", command=self.export_zip)
        file_menu.add_separator()
        file_menu.add_command(label="Close", command=self.on_close)
        self.popup_menus["File"] = file_menu

        if self._detect_project_type() == "lmr":
            self.popup_menus["LMR Resource Manager"] = self._build_lmr_resource_manager_menu(self.root)

        editor_menu = tk.Menu(self.root, tearoff=False, bg="#111111", fg="#d8d8d8", activebackground="#143c3d", activeforeground="#56f4ee", bd=0)
        editor_menu.add_command(label="Copy", command=self._copy_selected_text)
        editor_menu.add_command(label="Paste", command=self._paste_text)
        editor_menu.add_command(label="Cut", command=self._cut_selected_text)
        editor_menu.add_separator()
        editor_menu.add_command(label="Select All", command=self._select_all_text)
        self.editor_context_menu = editor_menu

    def _build_lmr_resource_manager_menu(self, parent_menu):
        menu = tk.Menu(parent_menu, tearoff=False, bg="#111111", fg="#d8d8d8", activebackground="#143c3d", activeforeground="#56f4ee", bd=0)
        menu.add_command(label="Add backdrop_bg", command=self.add_lmr_backdrop_bg)
        menu.add_command(label="Add backdrop_text", command=self.add_lmr_backdrop_text)
        menu.add_command(label="Add bg", command=self.add_lmr_bg)
        menu.add_command(label="Add cg", command=self.add_lmr_cg)
        menu.add_command(label="Add catalogs", command=self.add_lmr_catalogs)
        menu.add_command(label="Add colors", command=self.add_lmr_colors)
        menu.add_command(label="Add help", command=self.add_lmr_help)
        menu.add_command(label="Add notes", command=self.add_lmr_notes)
        menu.add_command(label="Add positions", command=self.add_lmr_positions)
        menu.add_command(label="Add sizes", command=self.add_lmr_sizes)
        menu.add_command(label="Add overlay color", command=self.add_lmr_spritecolor)
        menu.add_command(label="Add sound", command=self.add_lmr_sound)
        menu.add_command(label="Add transition", command=self.add_lmr_transition)
        menu.add_command(label="Add entryPoint", command=self.add_lmr_entry_point)
        menu.add_command(label="Add variable", command=self.add_lmr_variable)
        return menu

    def _render_top_menu_buttons(self):
        if self.canvas is None:
            return
        for item_id in self.top_menu_item_ids:
            try:
                self.canvas.delete(item_id)
            except tk.TclError:
                pass
        self.top_menu_item_ids.clear()

        menu = self.layout["menu"]
        self.top_menu_item_ids.append(self._create_text_button(menu["project_x"], menu["y"], "Project", self.open_project))
        self.top_menu_item_ids.append(self._create_text_button(menu["file_x"], menu["y"], "File", self.save_current_file))
        self.top_menu_item_ids.append(self._create_text_button(menu["settings_x"], menu["y"], "Settings", self.open_settings_window))
        if self._detect_project_type() == "lmr":
            self.top_menu_item_ids.append(self._create_text_button(menu["resource_manager_x"], menu["y"], "LMR Resource Manager", self.open_settings_window))

    def _create_text_button(self, x, y, text, command):
        item = self.canvas.create_text(x, y, anchor="nw", text=text, fill="#d3d7d5", font=("Segoe UI", 9), tags=(f"button_{text}",))
        if text == "Settings":
            self.canvas.tag_bind(item, "<Button-1>", lambda _event, callback=command: callback())
        else:
            self.canvas.tag_bind(item, "<Button-1>", lambda event, label=text, fallback=command: self._show_top_menu(event, label, fallback))
        self.canvas.tag_bind(item, "<Enter>", lambda _e, item_id=item: self.canvas.itemconfigure(item_id, fill="#56f4ee"))
        self.canvas.tag_bind(item, "<Leave>", lambda _e, item_id=item: self.canvas.itemconfigure(item_id, fill="#d3d7d5"))
        return item

    def _configure_editor_syntax_tags(self):
        if self.editor_text is None:
            return
        tag_colors = {
            "syntax_comment": "#6a9955",
            "syntax_string": "#ce9178",
            "syntax_number": "#b5cea8",
            "syntax_keyword": "#4fc1ff",
            "syntax_operator": "#d4d4d4",
            "syntax_section": "#c586c0",
            "syntax_boolean": "#569cd6",
            "syntax_property": "#9cdcfe",
        }
        for tag_name, color in tag_colors.items():
            self.editor_text.tag_configure(tag_name, foreground=color)

    def _clear_editor_syntax_tags(self):
        if self.editor_text is None:
            return
        for tag_name in (
            "syntax_comment",
            "syntax_string",
            "syntax_number",
            "syntax_keyword",
            "syntax_operator",
            "syntax_section",
            "syntax_boolean",
            "syntax_property",
        ):
            self.editor_text.tag_remove(tag_name, "1.0", "end")

    def _apply_tag_matches(self, tag_name: str, pattern: str, flags=0):
        if self.editor_text is None:
            return
        content = self._get_editor_content()
        for match in re.finditer(pattern, content, flags):
            start = f"1.0+{match.start()}c"
            end = f"1.0+{match.end()}c"
            self.editor_text.tag_add(tag_name, start, end)

    def _apply_editor_syntax_highlighting(self):
        if self.editor_text is None:
            return
        self._clear_editor_syntax_tags()
        path = self.current_file
        suffix = path.suffix.lower() if path is not None else ""
        content = self._get_editor_content()
        if not content:
            return

        self._apply_tag_matches("syntax_string", r'"([^"\\]|\\.)*"|\'([^\'\\]|\\.)*\'')
        self._apply_tag_matches("syntax_number", r'(?<![A-Za-z0-9_])[-+]?(?:\d+\.\d+|\d+)(?![A-Za-z0-9_])')

        if suffix in {".yaml", ".yml"}:
            self._apply_tag_matches("syntax_comment", r'(?m)^\s*#.*$')
            self._apply_tag_matches("syntax_section", r'(?m)^[A-Za-z_][A-Za-z0-9_]*\s*:(?=\s*$|\s)')
            self._apply_tag_matches("syntax_property", r'(?m)^\s{4,}[A-Za-z_][A-Za-z0-9_]*\s*:')
            self._apply_tag_matches("syntax_boolean", r'(?i)\b(?:true|false|null|yes|no|on|off)\b')
        elif suffix in {".json", ".toml"}:
            self._apply_tag_matches("syntax_property", r'(?m)"[^"\\]+"\s*:')
            self._apply_tag_matches("syntax_boolean", r'(?i)\b(?:true|false|null)\b')
        elif suffix in {".rpy", ".rpym", ".py", ".txt", ".md"}:
            self._apply_tag_matches("syntax_comment", r'(?m)#.*$')
            self._apply_tag_matches("syntax_keyword", r'\b(?:label|scene|show|hide|jump|call|menu|screen|init|define|default|transform|image|return|if|elif|else|python|while|for|in|pass|extends)\b')
            self._apply_tag_matches("syntax_boolean", r'\b(?:True|False|None)\b')
            self._apply_tag_matches("syntax_operator", r'\$|->|==|!=|<=|>=|=|:')
        else:
            self._apply_tag_matches("syntax_comment", r'(?m)#.*$')

    def _is_file_dirty(self, path: Path) -> bool:
        return self.file_buffers.get(path, "") != self.saved_file_snapshots.get(path, "")

    def _set_editor_content(self, content: str):
        if self.editor_text is None:
            return
        self.editor_text.delete("1.0", "end")
        self.editor_text.insert("1.0", content)
        self._apply_editor_scroll_space()
        self._apply_editor_syntax_highlighting()

    def _get_editor_content(self) -> str:
        if self.editor_text is None:
            return ""
        return self.editor_text.get("1.0", "end-1c")

    def _get_editor_line_count(self) -> int:
        content = self._get_editor_content()
        return max(1, content.count("\n") + 1)

    def _apply_editor_scroll_space(self):
        return

    def _update_current_buffer(self):
        if self.current_file is None or self.editor_text is None:
            return
        current_text = self._get_editor_content()
        self.file_buffers[self.current_file] = current_text
        if current_text == self.saved_file_snapshots.get(self.current_file, ""):
            self.dirty_files.discard(self.current_file)
        else:
            self.dirty_files.add(self.current_file)

    def _handle_editor_key_release(self, _event=None):
        self._update_current_buffer()
        self._apply_editor_syntax_highlighting()
        self._update_status(refresh_lines=True)
        self._request_render_file_tabs()

    def _get_selected_text(self) -> str:
        if self.editor_text is None:
            return ""
        try:
            return self.editor_text.get("sel.first", "sel.last")
        except tk.TclError:
            return ""

    def _copy_selected_text(self):
        if self.editor_text is None:
            return
        selected = self._get_selected_text()
        if not selected:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(selected)
        self._focus_editor_widget()

    def _cut_selected_text(self):
        if self.editor_text is None:
            return
        selected = self._get_selected_text()
        if not selected:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(selected)
        self.editor_text.delete("sel.first", "sel.last")
        self._handle_editor_key_release()
        self._focus_editor_widget()

    def _paste_text(self):
        if self.editor_text is None:
            return
        try:
            pasted = self.root.clipboard_get()
        except tk.TclError:
            pasted = ""
        if not pasted:
            self._focus_editor_widget()
            return
        try:
            if self.editor_text.tag_ranges("sel"):
                self.editor_text.delete("sel.first", "sel.last")
        except tk.TclError:
            pass
        self.editor_text.insert("insert", pasted)
        self._handle_editor_key_release()
        self._focus_editor_widget()

    def _select_all_text(self):
        if self.editor_text is None:
            return
        self.editor_text.tag_add("sel", "1.0", "end-1c")
        self.editor_text.mark_set("insert", "1.0")
        self.editor_text.see("insert")
        self._focus_editor_widget()

    def _show_editor_context_menu(self, event):
        if self.editor_text is None or self.editor_context_menu is None:
            return "break"
        selected = bool(self._get_selected_text())
        self.editor_context_menu.entryconfigure("Copy", state=("normal" if selected else "disabled"))
        self.editor_context_menu.entryconfigure("Cut", state=("normal" if selected else "disabled"))
        self.editor_context_menu.entryconfigure("Paste", state="normal")
        self.editor_context_menu.entryconfigure("Select All", state="normal")
        try:
            self.editor_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.editor_context_menu.grab_release()
        return "break"

    def _sync_editor_vertical_views(self, first, last=None):
        first_value = max(0.0, min(float(first), 1.0))
        last_value = first_value if last is None else max(first_value, min(float(last), 1.0))
        self.editor_scrollbar_view = (first_value, last_value)
        self._refresh_line_numbers(force=True)
        self._render_editor_scrollbar(first_value, last_value)

    def _sync_editor_horizontal_views(self, first, last=None):
        first_value = max(0.0, min(float(first), 1.0))
        last_value = first_value if last is None else max(first_value, min(float(last), 1.0))
        self.editor_h_scrollbar_view = (first_value, last_value)
        self._render_editor_h_scrollbar(first_value, last_value)

    def _scroll_editor_from_scrollbar(self, *args):
        if self.editor_text is None:
            return
        self.editor_text.yview(*args)
        self._update_status(refresh_lines=False)

    def _render_editor_scrollbar(self, first: float, last: float):
        if self.editor_scrollbar is None:
            return
        width = max(1, int(self.layout["editor_scrollbar"]["width"]))
        height = max(1, int(self.layout["editor_scrollbar"]["height"]))
        self.editor_scrollbar.delete("all")

        background = self._load_asset_exact("list_m.png", width, height)
        if background is not None:
            self.editor_scrollbar_images["background"] = background
            self.editor_scrollbar.create_image(0, 0, image=background, anchor="nw")

        visible_ratio = max(0.0, min(last - first, 1.0))
        thumb_height = int(round(height * visible_ratio))
        min_thumb_height = min(height, max(22, width))
        thumb_height = max(min_thumb_height, min(height, thumb_height))
        max_thumb_y = max(0, height - thumb_height)
        max_first = max(0.0, 1.0 - visible_ratio)
        normalized_first = 0.0 if max_first <= 0.0 else max(0.0, min(first / max_first, 1.0))
        thumb_y = int(round(max_thumb_y * normalized_first))
        thumb_y = max(0, min(max_thumb_y, thumb_y))

        state_suffix = "clicked" if self.editor_scrollbar_pressed else ("onmouse" if self.editor_scrollbar_hovered else "")
        top_name = f"list_track_{state_suffix + '_' if state_suffix else ''}t.png"
        middle_name = f"list_track_{state_suffix + '_' if state_suffix else ''}m.png"
        bottom_name = f"list_track_{state_suffix + '_' if state_suffix else ''}b.png"

        cap_height = min(22, max(1, thumb_height // 2))
        top_height = cap_height
        bottom_height = cap_height if thumb_height > 1 else 1
        if top_height + bottom_height > thumb_height:
            bottom_height = max(1, thumb_height - top_height)
        middle_height = max(0, thumb_height - top_height - bottom_height)

        thumb_top = self._load_asset_exact(top_name, width, top_height)
        thumb_bottom = self._load_asset_exact(bottom_name, width, bottom_height)
        middle_y = thumb_y + top_height
        thumb_middle = self._load_asset_exact(middle_name, width, middle_height) if middle_height > 0 else None

        self.editor_scrollbar_thumb = (thumb_y, thumb_y + thumb_height)
        if thumb_top is not None:
            self.editor_scrollbar_images["thumb_top"] = thumb_top
            self.editor_scrollbar.create_image(0, thumb_y, image=thumb_top, anchor="nw", tags=("scrollbar_thumb",))
        if thumb_middle is not None:
            self.editor_scrollbar_images["thumb_middle"] = thumb_middle
            self.editor_scrollbar.create_image(0, middle_y, image=thumb_middle, anchor="nw", tags=("scrollbar_thumb",))
        if thumb_bottom is not None:
            self.editor_scrollbar_images["thumb_bottom"] = thumb_bottom
            self.editor_scrollbar.create_image(0, thumb_y + thumb_height - bottom_height, image=thumb_bottom, anchor="nw", tags=("scrollbar_thumb",))

    def _is_pointer_over_scrollbar_thumb(self, y: int) -> bool:
        thumb = self.editor_scrollbar_thumb
        if thumb is None:
            return False
        return thumb[0] <= y <= thumb[1]

    def _render_editor_h_scrollbar(self, first: float, last: float):
        if self.editor_h_scrollbar is None:
            return
        width = max(1, int(self.layout["editor_h_scrollbar"]["width"]))
        height = max(1, int(self.layout["editor_h_scrollbar"]["height"]))
        self.editor_h_scrollbar.delete("all")

        background = self._load_asset_exact("list_m_horz.png", width, height)
        if background is not None:
            self.editor_h_scrollbar_images["background"] = background
            self.editor_h_scrollbar.create_image(0, 0, image=background, anchor="nw")

        visible_ratio = max(0.0, min(last - first, 1.0))
        thumb_width = int(round(width * visible_ratio))
        min_thumb_width = min(width, max(22, height))
        thumb_width = max(min_thumb_width, min(width, thumb_width))
        max_thumb_x = max(0, width - thumb_width)
        max_first = max(0.0, 1.0 - visible_ratio)
        normalized_first = 0.0 if max_first <= 0.0 else max(0.0, min(first / max_first, 1.0))
        thumb_x = int(round(max_thumb_x * normalized_first))
        thumb_x = max(0, min(max_thumb_x, thumb_x))

        state_suffix = "clicked" if self.editor_h_scrollbar_pressed else ("onmouse" if self.editor_h_scrollbar_hovered else "")
        left_name = f"list_track_{state_suffix + '_' if state_suffix else ''}b_horz.png"
        middle_name = f"list_track_{state_suffix + '_' if state_suffix else ''}m_horz.png"
        right_name = f"list_track_{state_suffix + '_' if state_suffix else ''}t_horz.png"

        cap_width = min(22, max(1, thumb_width // 2))
        left_width = cap_width
        right_width = cap_width if thumb_width > 1 else 1
        if left_width + right_width > thumb_width:
            right_width = max(1, thumb_width - left_width)
        middle_width = max(0, thumb_width - left_width - right_width)

        thumb_left = self._load_asset_exact(left_name, left_width, height)
        thumb_middle = self._load_asset_exact(middle_name, middle_width, height) if middle_width > 0 else None
        thumb_right = self._load_asset_exact(right_name, right_width, height)

        self.editor_h_scrollbar_thumb = (thumb_x, thumb_x + thumb_width)
        if thumb_left is not None:
            self.editor_h_scrollbar_images["thumb_left"] = thumb_left
            self.editor_h_scrollbar.create_image(thumb_x, 0, image=thumb_left, anchor="nw", tags=("scrollbar_thumb_h",))
        if thumb_middle is not None:
            self.editor_h_scrollbar_images["thumb_middle"] = thumb_middle
            self.editor_h_scrollbar.create_image(thumb_x + left_width, 0, image=thumb_middle, anchor="nw", tags=("scrollbar_thumb_h",))
        if thumb_right is not None:
            self.editor_h_scrollbar_images["thumb_right"] = thumb_right
            self.editor_h_scrollbar.create_image(thumb_x + thumb_width - right_width, 0, image=thumb_right, anchor="nw", tags=("scrollbar_thumb_h",))

    def _is_pointer_over_h_scrollbar_thumb(self, x: int) -> bool:
        thumb = self.editor_h_scrollbar_thumb
        if thumb is None:
            return False
        return thumb[0] <= x <= thumb[1]

    def _move_editor_to_h_scroll_fraction(self, fraction: float):
        if self.editor_text is None:
            return
        first, last = self.editor_h_scrollbar_view
        visible_ratio = max(0.0, min(last - first, 1.0))
        max_first = max(0.0, 1.0 - visible_ratio)
        normalized_fraction = max(0.0, min(fraction, 1.0))
        self.editor_text.xview_moveto(max_first * normalized_fraction)
        self._update_status(refresh_lines=False)

    def _move_editor_to_scroll_fraction(self, fraction: float):
        if self.editor_text is None:
            return
        first, last = self.editor_scrollbar_view
        visible_ratio = max(0.0, min(last - first, 1.0))
        max_first = max(0.0, 1.0 - visible_ratio)
        normalized_fraction = max(0.0, min(fraction, 1.0))
        self.editor_text.yview_moveto(max_first * normalized_fraction)
        self._update_status(refresh_lines=False)

    def _handle_editor_scrollbar_press(self, event):
        if self.editor_scrollbar is None:
            return "break"
        thumb = self.editor_scrollbar_thumb
        if thumb is None:
            return "break"
        thumb_top, thumb_bottom = thumb
        if thumb_top <= event.y <= thumb_bottom:
            self.editor_scrollbar_thumb_offset_y = event.y - thumb_top
            self.editor_scrollbar_pressed = True
            self.editor_scrollbar_hovered = True
            self._render_editor_scrollbar(*self.editor_scrollbar_view)
            return "break"
        height = max(1, int(self.layout["editor_scrollbar"]["height"]))
        thumb_height = max(1, thumb_bottom - thumb_top)
        target_fraction = (event.y - (thumb_height / 2)) / max(1, height - thumb_height)
        self.editor_scrollbar_thumb_offset_y = thumb_height / 2
        self.editor_scrollbar_pressed = True
        self.editor_scrollbar_hovered = self._is_pointer_over_scrollbar_thumb(event.y)
        self._move_editor_to_scroll_fraction(target_fraction)
        self._render_editor_scrollbar(*self.editor_scrollbar_view)
        return "break"

    def _handle_editor_scrollbar_drag(self, event):
        thumb = self.editor_scrollbar_thumb
        if thumb is None:
            return "break"
        height = max(1, int(self.layout["editor_scrollbar"]["height"]))
        thumb_height = max(1, thumb[1] - thumb[0])
        target_fraction = (event.y - self.editor_scrollbar_thumb_offset_y) / max(1, height - thumb_height)
        self.editor_scrollbar_pressed = True
        self.editor_scrollbar_hovered = True
        self._move_editor_to_scroll_fraction(target_fraction)
        self._render_editor_scrollbar(*self.editor_scrollbar_view)
        return "break"

    def _handle_editor_scrollbar_release(self, _event=None):
        self.editor_scrollbar_thumb_offset_y = 0
        self.editor_scrollbar_pressed = False
        self._render_editor_scrollbar(*self.editor_scrollbar_view)
        return "break"

    def _handle_editor_scrollbar_motion(self, event):
        hovered = self._is_pointer_over_scrollbar_thumb(int(getattr(event, "y", 0)))
        if hovered != self.editor_scrollbar_hovered and not self.editor_scrollbar_pressed:
            self.editor_scrollbar_hovered = hovered
            self._render_editor_scrollbar(*self.editor_scrollbar_view)

    def _handle_editor_scrollbar_leave(self, _event=None):
        if self.editor_scrollbar_pressed:
            return
        if self.editor_scrollbar_hovered:
            self.editor_scrollbar_hovered = False
            self._render_editor_scrollbar(*self.editor_scrollbar_view)

    def _handle_editor_h_scrollbar_press(self, event):
        if self.editor_h_scrollbar is None:
            return "break"
        thumb = self.editor_h_scrollbar_thumb
        if thumb is None:
            return "break"
        thumb_left, thumb_right = thumb
        if thumb_left <= event.x <= thumb_right:
            self.editor_h_scrollbar_thumb_offset_x = event.x - thumb_left
            self.editor_h_scrollbar_pressed = True
            self.editor_h_scrollbar_hovered = True
            self._render_editor_h_scrollbar(*self.editor_h_scrollbar_view)
            return "break"
        width = max(1, int(self.layout["editor_h_scrollbar"]["width"]))
        thumb_width = max(1, thumb_right - thumb_left)
        target_fraction = (event.x - (thumb_width / 2)) / max(1, width - thumb_width)
        self.editor_h_scrollbar_thumb_offset_x = thumb_width / 2
        self.editor_h_scrollbar_pressed = True
        self.editor_h_scrollbar_hovered = self._is_pointer_over_h_scrollbar_thumb(event.x)
        self._move_editor_to_h_scroll_fraction(target_fraction)
        self._render_editor_h_scrollbar(*self.editor_h_scrollbar_view)
        return "break"

    def _handle_editor_h_scrollbar_drag(self, event):
        thumb = self.editor_h_scrollbar_thumb
        if thumb is None:
            return "break"
        width = max(1, int(self.layout["editor_h_scrollbar"]["width"]))
        thumb_width = max(1, thumb[1] - thumb[0])
        target_fraction = (event.x - self.editor_h_scrollbar_thumb_offset_x) / max(1, width - thumb_width)
        self.editor_h_scrollbar_pressed = True
        self.editor_h_scrollbar_hovered = True
        self._move_editor_to_h_scroll_fraction(target_fraction)
        self._render_editor_h_scrollbar(*self.editor_h_scrollbar_view)
        return "break"

    def _handle_editor_h_scrollbar_release(self, _event=None):
        self.editor_h_scrollbar_thumb_offset_x = 0
        self.editor_h_scrollbar_pressed = False
        self._render_editor_h_scrollbar(*self.editor_h_scrollbar_view)
        return "break"

    def _handle_editor_h_scrollbar_motion(self, event):
        hovered = self._is_pointer_over_h_scrollbar_thumb(int(getattr(event, "x", 0)))
        if hovered != self.editor_h_scrollbar_hovered and not self.editor_h_scrollbar_pressed:
            self.editor_h_scrollbar_hovered = hovered
            self._render_editor_h_scrollbar(*self.editor_h_scrollbar_view)

    def _handle_editor_h_scrollbar_leave(self, _event=None):
        if self.editor_h_scrollbar_pressed:
            return
        if self.editor_h_scrollbar_hovered:
            self.editor_h_scrollbar_hovered = False
            self._render_editor_h_scrollbar(*self.editor_h_scrollbar_view)

    def _scroll_editor_from_line_numbers(self, event):
        if self.editor_text is None:
            return "break"
        if getattr(event, "num", None) == 4:
            self.editor_text.yview_scroll(-1, "units")
        elif getattr(event, "num", None) == 5:
            self.editor_text.yview_scroll(1, "units")
        else:
            delta = getattr(event, "delta", 0)
            if delta != 0:
                self.editor_text.yview_scroll(int(-delta / 120), "units")
        self._update_status(refresh_lines=False)
        return "break"

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
            for tag in self.file_tab_tags:
                try:
                    self.canvas.delete(tag)
                except tk.TclError:
                    pass
            for item_id in self.file_tab_item_ids:
                try:
                    self.canvas.delete(item_id)
                except tk.TclError:
                    pass
            for item_id in self.file_tab_window_ids:
                try:
                    self.canvas.delete(item_id)
                except tk.TclError:
                    pass
        self.file_tab_tags.clear()
        self.file_tab_item_ids.clear()
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

    def _schedule_switch_to_file(self, path: Path):
        if self.root is None:
            return "break"
        self.root.after_idle(lambda p=path: self.switch_to_file(p))
        return "break"

    def _schedule_close_file_tab(self, path: Path):
        if self.root is None:
            return "break"
        self.root.after_idle(lambda p=path: self.close_file_tab(p))
        return "break"

    def _render_file_tabs(self):
        if self.canvas is None:
            return
        self._clear_file_tabs()
        layout = self.layout["file_tabs"]
        x = layout["x"]
        y = layout["y"]
        gap = layout["gap"]
        height = layout["height"]
        for index, path in enumerate(self.open_files):
            total_width, item_ids = self._create_file_tab_items(path, x, y, height, index)
            self.file_tab_item_ids.extend(item_ids)
            self.file_tab_tags.extend((f"filetab_{index}_body", f"filetab_{index}_close"))
            x += total_width + gap

    def _create_file_tab_items(self, path: Path, x: int, y: int, height: int, index: int):
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
        item_ids = []
        tag_base = f"filetab_{index}"
        tab_tag = f"{tag_base}_body"
        close_tag = f"{tag_base}_close"

        def state_assets(state_name: str):
            return (
                self._load_asset_exact(f"tab_{state_name}_l.png", left_width, height),
                self._load_asset_exact(f"tab_{state_name}_m.png", estimated_middle, height),
                self._load_asset_exact(f"tab_{state_name}_r.png", right_width, height),
            )

        def draw_state(state_name: str, close_state: str = "idle"):
            self.canvas.delete(tab_tag)
            self.canvas.delete(close_tag)
            item_ids.clear()
            left, middle, right = state_assets(state_name)
            text_color = layout["active_text_color"] if path == self.current_file else layout["inactive_text_color"]
            item_ids.append(self.canvas.create_rectangle(x, y, x + total_width, y + height, fill=PANEL_BACKGROUND, outline=PANEL_BACKGROUND, tags=(tab_tag,)))
            if left is not None:
                item_ids.append(self.canvas.create_image(x, y, image=left, anchor="nw", tags=(tab_tag,)))
            if middle is not None:
                item_ids.append(self.canvas.create_image(x + left_width, y, image=middle, anchor="nw", tags=(tab_tag,)))
            if right is not None:
                item_ids.append(self.canvas.create_image(x + left_width + estimated_middle, y, image=right, anchor="nw", tags=(tab_tag,)))
            item_ids.append(
                self.canvas.create_text(
                    x + ((total_width - close_reserved) // 2),
                    y + (height // 2),
                    text=label,
                    fill=text_color,
                    font=("Cascadia Mono", 9, "bold"),
                    tags=(tab_tag,),
                )
            )
            close_icon = self._load_asset_exact(
                f"exit_btn_{close_state}.png",
                max(10, height - 6),
                max(10, height - 6),
            )
            if close_icon is not None:
                item_ids.append(
                    self.canvas.create_image(
                        x + total_width - layout["close_padding_right"],
                        y + (height // 2),
                        image=close_icon,
                        anchor="center",
                        tags=(close_tag,),
                    )
                )
            self.canvas.tag_bind(tab_tag, "<Button-1>", lambda _e, p=path: self._schedule_switch_to_file(p))
            self.canvas.tag_bind(close_tag, "<Button-1>", lambda _e, p=path: self._schedule_close_file_tab(p))

        draw_state(state, "idle")
        return total_width, item_ids

    def _create_image_button(self, x, y, idle_name, hover_name, pressed_name, command):
        item = self.canvas.create_image(x, y, anchor="nw", image=self.assets.get(idle_name))
        self.canvas.tag_bind(item, "<Enter>", lambda _e, item_id=item: self.canvas.itemconfigure(item_id, image=self.assets.get(hover_name)))
        self.canvas.tag_bind(item, "<Leave>", lambda _e, item_id=item: self.canvas.itemconfigure(item_id, image=self.assets.get(idle_name)))
        self.canvas.tag_bind(item, "<ButtonPress-1>", lambda _e, item_id=item: self.canvas.itemconfigure(item_id, image=self.assets.get(pressed_name)))
        self.canvas.tag_bind(item, "<ButtonRelease-1>", lambda _e, item_id=item: self.canvas.itemconfigure(item_id, image=self.assets.get(hover_name)))
        self.canvas.tag_bind(item, "<Button-1>", lambda _e: command())
        return item

    def _create_composite_button(self, parent_window, parent_canvas, x, y, label, middle_width, button_height, action, alpha=1.0):
        left_idle = self.assets.get("button_border_left_idle.png")
        right_idle = self.assets.get("button_border_right_idle.png")
        if left_idle is None or right_idle is None:
            return None, None

        left_width = max(1, int(round(left_idle.width() * (button_height / max(1, left_idle.height())))))
        right_width = max(1, int(round(right_idle.width() * (button_height / max(1, right_idle.height())))))
        height = max(1, button_height)
        total_width = left_width + middle_width + right_width
        widget = tk.Canvas(parent_window, width=total_width, height=height, bg=TRANSPARENT_COLOR, highlightthickness=0, bd=0)
        widget._state_images = {}  # type: ignore[attr-defined]

        def build_state(state_name: str):
            left = self._load_asset_exact_alpha(f"button_border_left_{state_name}.png", left_width, height, alpha)
            middle = self._load_asset_exact_alpha(f"button_middle_{state_name}.png", middle_width, height, alpha)
            right = self._load_asset_exact_alpha(f"button_border_right_{state_name}.png", right_width, height, alpha)
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
        if parent_canvas is None:
            widget.place(x=x, y=y, width=total_width, height=height)
            window_item = None
        else:
            window_item = parent_canvas.create_window(x, y, anchor="nw", window=widget, width=total_width, height=height)
        return widget, window_item

    def _draw_window_frame(self, canvas, width, height):
        edge = 22
        background = self._load_asset_exact("window_back.png", max(1, width - edge * 2), max(1, height - edge * 2))
        if background is not None:
            canvas.create_image(edge, edge, image=background, anchor="nw")
            if not hasattr(canvas, "_frame_images"):
                canvas._frame_images = []  # type: ignore[attr-defined]
            canvas._frame_images.append(background)  # type: ignore[attr-defined]
        else:
            canvas.create_rectangle(edge, edge, width - edge, height - edge, fill="#101010", outline="")

        pieces = [
            ("window_lt.png", 0, 0, edge, edge),
            ("window_rt.png", width - edge, 0, edge, edge),
            ("window_lb.png", 0, height - edge, edge, edge),
            ("window_rb.png", width - edge, height - edge, edge, edge),
            ("window_t.png", edge, 0, max(1, width - edge * 2), edge),
            ("window_b.png", edge, height - edge, max(1, width - edge * 2), edge),
            ("window_l.png", 0, edge, edge, max(1, height - edge * 2)),
            ("window_r.png", width - edge, edge, edge, max(1, height - edge * 2)),
        ]

        for name, x, y, w, h in pieces:
            image = self._load_asset_exact(name, w, h)
            if image is None:
                continue
            canvas.create_image(x, y, image=image, anchor="nw")
            if not hasattr(canvas, "_frame_images"):
                canvas._frame_images = []  # type: ignore[attr-defined]
            canvas._frame_images.append(image)  # type: ignore[attr-defined]

    def _show_unsaved_warning(self, title: str, message: str) -> bool:
        if self.confirm_window is not None and self.confirm_window.winfo_exists():
            try:
                self.confirm_window.destroy()
            except tk.TclError:
                pass
        result = {"exit": False}
        width = 420
        height = 210
        parent_window = self.settings_window if self.settings_window is not None and self.settings_window.winfo_exists() else self.root

        window = tk.Toplevel(parent_window)
        self.confirm_window = window
        window.transient(parent_window)
        window.resizable(False, False)
        window.configure(bg=TRANSPARENT_COLOR)
        window.overrideredirect(True)
        try:
            window.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)
        except tk.TclError:
            pass
        try:
            window.wm_attributes("-topmost", True)
        except tk.TclError:
            pass
        window.geometry(
            f"{width}x{height}+{parent_window.winfo_x() + max(0, (parent_window.winfo_width() - width) // 2)}+{parent_window.winfo_y() + max(0, (parent_window.winfo_height() - height) // 2)}"
        )
        window.bind("<Escape>", lambda _e: close_dialog(False))
        canvas = tk.Canvas(window, width=width, height=height, bg=TRANSPARENT_COLOR, highlightthickness=0, bd=0)
        canvas.pack()
        self._draw_window_frame(canvas, width, height)
        canvas.create_text(width // 2, 42, text=title, anchor="n", fill="#f0f0f0", font=("Cascadia Mono", 12, "bold"))
        canvas.create_text(
            width // 2,
            86,
            text=message,
            anchor="n",
            fill="#d7d9d7",
            font=("Cascadia Mono", 9, "bold"),
            justify="center",
            width=width - 56,
        )

        def close_dialog(should_exit: bool):
            result["exit"] = should_exit
            if self.confirm_window is not None and self.confirm_window.winfo_exists():
                try:
                    self.confirm_window.grab_release()
                except tk.TclError:
                    pass
                self.confirm_window.destroy()
            self.confirm_window = None
            try:
                parent_window.focus_force()
            except tk.TclError:
                pass
            if parent_window is self.root:
                self._focus_editor_widget()

        self._create_composite_button(window, canvas, 90, 150, "Return", 80, 24, lambda: close_dialog(False))
        self._create_composite_button(window, canvas, 240, 150, "Exit", 80, 24, lambda: close_dialog(True))
        window.grab_set()
        window.deiconify()
        window.lift()
        window.focus_force()
        window.wait_window()
        return bool(result["exit"])

    def _bind_shortcuts(self):
        self.root.bind("<Escape>", lambda _e: self.on_close())
        self.root.bind_all("<KeyPress>", self._handle_shortcut_keypress)

    def _focus_editor_widget(self, _event=None):
        if self.editor_text is None:
            return
        try:
            self.editor_text.configure(state="normal")
        except tk.TclError:
            pass
        self.editor_text.focus_set()

    def _insert_editor_spaces(self, _event=None):
        if self.editor_text is None:
            return "break"
        try:
            self.editor_text.insert("insert", " " * 4)
        except tk.TclError:
            return "break"
        self._handle_editor_key_release()
        return "break"

    def _save_shortcut(self, _event=None):
        self.save_current_file()
        self._focus_editor_widget()
        return "break"

    def _handle_shortcut_keypress(self, event):
        ctrl_pressed = bool(getattr(event, "state", 0) & 0x4)
        if not ctrl_pressed:
            return
        keysym = str(getattr(event, "keysym", "")).lower()
        keycode = int(getattr(event, "keycode", 0) or 0)
        if keysym == "c" or keycode == 67:
            self._copy_selected_text()
            return "break"
        if keysym == "v" or keycode == 86:
            self._paste_text()
            return "break"
        if keysym == "a" or keycode == 65:
            self._select_all_text()
            return "break"
        if keysym == "s" or keycode == 83:
            return self._save_shortcut(event)
        if keysym == "z" or keycode == 90:
            shift_pressed = bool(getattr(event, "state", 0) & 0x1)
            if shift_pressed:
                return self._redo_action(event)
            return self._undo_action(event)
        if keysym == "y" or keycode == 89:
            return self._redo_action(event)
        if keysym == "o" or keycode == 79:
            return self._open_project_shortcut(event)
        if keysym == "w" or keycode == 87:
            return self._close_tab_shortcut(event)
        return

    def _open_project_shortcut(self, _event=None):
        self.open_project()
        return "break"

    def _close_tab_shortcut(self, _event=None):
        if self.current_file is not None:
            self.close_file_tab(self.current_file)
        return "break"

    def _undo_action(self, _event=None):
        if self.editor_text is None:
            return "break"
        try:
            self.editor_text.edit_undo()
        except tk.TclError:
            return "break"
        self._handle_editor_key_release()
        self._focus_editor_widget()
        return "break"

    def _redo_action(self, _event=None):
        if self.editor_text is None:
            return "break"
        try:
            self.editor_text.edit_redo()
        except tk.TclError:
            return "break"
        self._handle_editor_key_release()
        self._focus_editor_widget()
        return "break"

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
        self.settings_vars["default_lmr_game_dir"] = tk.StringVar(value=self.app_settings.get("default_lmr_game_dir", ""))
        self.settings_vars["default_es_game_dir"] = tk.StringVar(value=self.app_settings.get("default_es_game_dir", ""))

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
        self._render_text_block([f"SGME Build {APP_BUILD_NUMBER}"], 118, 444, font=("Cascadia Mono", 14, "bold"))
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
        self._render_settings_path_row(0, 24, "Default LMR Game Folder", self.settings_vars["default_lmr_game_dir"], "Select default Love, Money, Rock'n'Roll folder")
        self._render_settings_path_row(0, 84, "Default ES Game Folder", self.settings_vars["default_es_game_dir"], "Select default Everlasting Summer folder")
        self._render_action_button("save_settings", "Save Settings", 0, 144, self._save_settings)
        self._render_action_button("open_app_settings", "Open App Settings", 0, 184, lambda: self._open_path_in_system(APP_SETTINGS_PATH))

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
        widget, window_item = self._create_composite_button(
            self.settings_window,
            self.settings_canvas,
            x,
            y,
            label,
            middle_width,
            button_height,
            action,
            alpha=button_alpha,
        )
        if widget is None or window_item is None:
            return
        self.settings_action_widgets.append(widget)
        self.settings_content_items.append(window_item)

    def _render_settings_path_row(self, rel_x, rel_y, label, variable, browse_title):
        x, y = self._content_anchor(rel_x, rel_y)
        label_item = self.settings_canvas.create_text(x, y, text=label, anchor="nw", fill="#f0f0f0", font=("Cascadia Mono", 9, "bold"))
        self.settings_content_items.append(label_item)

        entry = tk.Entry(
            self.settings_window,
            textvariable=variable,
            font=("Cascadia Mono", 8),
            bg="#101010",
            fg="#f0f0f0",
            insertbackground="#56f4ee",
            bd=0,
            highlightthickness=1,
            highlightbackground="#1d1d1d",
        )
        entry_item = self.settings_canvas.create_window(x, y + 24, anchor="nw", window=entry, width=186, height=24)
        self.settings_action_widgets.append(entry)
        self.settings_content_items.append(entry_item)

        def browse():
            try:
                self.settings_window.wm_attributes("-topmost", False)
            except tk.TclError:
                pass
            try:
                folder = filedialog.askdirectory(title=browse_title, parent=self.settings_window, initialdir=variable.get() or str(BASE_DIR))
            finally:
                try:
                    self.settings_window.wm_attributes("-topmost", True)
                    self.settings_window.lift()
                    self.settings_window.focus_force()
                except tk.TclError:
                    pass
            if folder:
                variable.set(folder)

        self._render_action_button("save_settings", "Browse", rel_x + 194, rel_y + 24, browse)

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
                    f"SGME Build {APP_BUILD_NUMBER}",
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
        try:
            self.root.focus_force()
        except tk.TclError:
            pass
        if self.editor_text is not None:
            self._focus_editor_widget()

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

        for key in ("line_numbers", "editor_scrollbar", "editor_h_scrollbar", "files"):
            block = layout[key]
            block_width = max(10, min(int(block.get("width", DEFAULT_LAYOUT[key]["width"])), width))
            block_height = max(10, min(int(block.get("height", DEFAULT_LAYOUT[key]["height"])), height))
            block_x = max(0, min(int(block.get("x", DEFAULT_LAYOUT[key]["x"])), width - block_width))
            block_y = max(0, min(int(block.get("y", DEFAULT_LAYOUT[key]["y"])), height - block_height))
            block["x"] = block_x
            block["y"] = block_y
            block["width"] = block_width
            block["height"] = block_height

        editor_block = layout["editor"]
        editor_width = max(10, min(int(editor_block.get("width", DEFAULT_LAYOUT["editor"]["width"])), width))
        editor_height = max(10, min(int(editor_block.get("height", DEFAULT_LAYOUT["editor"]["height"])), height))
        editor_x = max(0, min(int(editor_block.get("x", DEFAULT_LAYOUT["editor"]["x"])), width - editor_width))
        editor_y = max(0, min(int(editor_block.get("y", DEFAULT_LAYOUT["editor"]["y"])), height - editor_height))
        editor_block["x"] = editor_x
        editor_block["y"] = editor_y
        editor_block["width"] = editor_width
        editor_block["height"] = editor_height

        layout["header"]["x"] = max(0, min(int(layout["header"].get("x", DEFAULT_LAYOUT["header"]["x"])), width - 20))
        layout["header"]["y"] = max(0, min(int(layout["header"].get("y", DEFAULT_LAYOUT["header"]["y"])), height - 20))
        layout["status"]["mode_x"] = max(0, min(int(layout["status"].get("mode_x", DEFAULT_LAYOUT["status"]["mode_x"])), width - 20))
        layout["status"]["mode_y"] = max(0, min(int(layout["status"].get("mode_y", DEFAULT_LAYOUT["status"]["mode_y"])), height - 20))
        layout["status"]["cursor_x"] = max(0, min(int(layout["status"].get("cursor_x", DEFAULT_LAYOUT["status"]["cursor_x"])), width - 20))
        layout["status"]["cursor_y"] = max(0, min(int(layout["status"].get("cursor_y", DEFAULT_LAYOUT["status"]["cursor_y"])), height - 20))

        for name in ("project_x", "file_x", "settings_x", "resource_manager_x"):
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

        create_project = layout["create_project_window"]
        default_create_project = DEFAULT_LAYOUT["create_project_window"]
        for key in (
            "width",
            "height",
            "title_x",
            "title_y",
            "game_label_x",
            "game_label_y",
            "game_x",
            "game_y",
            "game_step_y",
            "menu_label_x",
            "menu_label_y",
            "menu_x",
            "menu_y",
            "menu_step_y",
            "game_item_width",
            "menu_item_width",
            "content_x",
            "content_y",
            "content_width",
            "content_height",
            "actions_y",
            "return_x",
            "create_x",
        ):
            create_project[key] = int(create_project.get(key, default_create_project[key]))
        for section_name in ("general", "lmr", "es"):
            if not isinstance(create_project.get(section_name), dict):
                create_project[section_name] = {}
            for key, default_value in default_create_project[section_name].items():
                create_project[section_name][key] = int(create_project[section_name].get(key, default_value))

        create_file = layout["create_file_window"]
        default_create_file = DEFAULT_LAYOUT["create_file_window"]
        for key, default_value in default_create_file.items():
            create_file[key] = int(create_file.get(key, default_value))

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
        editor_content = self._get_editor_content() if self.editor_text is not None else ""
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
            self._set_editor_content(self.file_buffers.get(self.current_file, editor_content))
            self.editor_text.mark_set("insert", cursor_index)
            self.editor_text.see(cursor_index)
        self._update_status()
        self._request_render_file_tabs()
        self._schedule_line_numbers_refresh()

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

    def _set_project_dir(self, path: Path):
        self.project_dir = path
        self.open_files.clear()
        self.file_buffers.clear()
        self.saved_file_snapshots.clear()
        self.dirty_files.clear()
        self.current_file = None
        self._build_popup_menus()
        self._render_top_menu_buttons()
        self._reload_project_files()
        self._update_status()
        self._update_presence()
        self._request_render_file_tabs()

    def _get_project_game_name(self) -> str:
        project_type = self._detect_project_type()
        if project_type == "lmr":
            return "Love, Money, Rock'n'Roll"
        if project_type == "es":
            return "Everlasting Summer"
        return "No project open"

    def _get_lmr_project_display_name(self) -> str | None:
        if self.project_dir is None:
            return None
        meta_path = self.project_dir / "meta.yaml"
        if not meta_path.exists():
            return None
        try:
            lines = meta_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return None
        in_title = False
        for line in lines:
            stripped = line.strip()
            if stripped == "title:":
                in_title = True
                continue
            if in_title and stripped and not line.startswith(" "):
                break
            if in_title and stripped.startswith("ru:"):
                value = stripped.split(":", 1)[1].strip().strip('"').strip("'")
                return value or None
        return None

    def _get_es_project_display_name(self) -> str | None:
        if self.project_dir is None:
            return None
        for path in sorted(self.project_dir.glob("*.rpy")):
            try:
                content = path.read_text(encoding="utf-8")
            except OSError:
                continue
            match = re.search(r"""mods\[['"][^'"]+['"]\]\s*=\s*u?['"](.+?)['"]""", content)
            if match:
                return match.group(1).strip()
        return None

    def _get_presence_project_name(self) -> str:
        project_type = self._detect_project_type()
        if project_type == "lmr":
            return self._get_lmr_project_display_name() or (self.project_dir.name if self.project_dir else "No project open")
        if project_type == "es":
            return self._get_es_project_display_name() or (self.project_dir.name if self.project_dir else "No project open")
        return self.project_dir.name if self.project_dir else "No project open"

    def _slugify_project_id(self, value: str) -> str:
        slug = re.sub(r"[^a-z0-9_]+", "_", value.lower())
        slug = re.sub(r"_+", "_", slug).strip("_")
        return slug or "new_mod"

    def _is_valid_project_id(self, value: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z0-9_]+", value))

    def _build_lmr_resources_yaml(self, selected_sections: list[str]) -> str:
        section_templates = {
            "backdrop_bg": "backdrop_bg:\n    sample_backdrop: backdrops/sample_backdrop.png",
            "backdrop_text": "backdrop_text:\n    sample_backdrop:\n        ru: \"Текст для backdrop\"",
            "bg": "bg:\n    ext_street_day: bg/ext_street_day.jpg",
            "cg": "cg:\n    event_intro: cg/event_intro.jpg",
            "catalogs": "catalogs:\n    bundle: catalogs/bundle/catalog.json",
            "characters": "characters:\n    hero:\n        poses:\n            normal:\n                parts:\n                    body: sprites/hero/body.png",
            "chibis": "chibis:\n    hero_smile: chibis/hero_smile.png",
            "collections": "collections:\n    bg:\n        sample_bg:\n            name: ext_street_day\n    music:\n        sample_track:\n            name: menu_theme",
            "colors": "colors:\n    accent: \"#56F4EE\"",
            "entryPoint": "entryPoint: main",
            "help": "help:\n    credits:\n        ru: \"Титры мода\"\n    contacts:\n        ru: \"Контакты мода\"",
            "live2d_characters": "live2d_characters:\n    hero:\n        poses:\n            idle:\n                asset: live2d/hero_idle",
            "menu": "menu:\n    bg:\n        0:\n            asset: bg/menu_bg.jpg\n    logos:\n        0:\n            asset: default\n    tracks:\n        0:\n            asset: sound/menu_theme.ogg",
            "particles": "particles:\n    sakura: particles/sakura.prefab",
            "positions": "positions:\n    custom_center:\n        x: 0.5\n        y: 0.5",
            "scenarios": "scenarios:",
            "sizes": "sizes:\n    custom_normal:\n        x: 1.0\n        y: 1.0",
            "sound": "sound:\n    menu_theme: sound/menu_theme.ogg",
            "spritecolor": "spritecolor:\n    sunset_tint: \"#FFB34766\"",
            "transitions": "transitions:\n    flash_fast:\n        preset: flash\n        duration: 0.2",
            "variables": "variables:\n    intro_seen: false\n    love_points: 0",
        }
        lines = ["---"]
        for key in selected_sections:
            template = section_templates.get(key)
            if template:
                if len(lines) > 1:
                    lines.append("")
                lines.append(template)
        return "\n".join(lines).strip() + "\n"

    def _build_lmr_meta_yaml(self, title: str, description: str, version: str, cover_rel_path: str | None) -> str:
        lines = [
            "---",
            "title:",
            f"    ru: {json.dumps(title, ensure_ascii=False)}",
            "",
            "description:",
            f"    ru: {json.dumps(description, ensure_ascii=False)}",
            "",
            f"version: {json.dumps(version, ensure_ascii=False)}",
        ]
        if cover_rel_path:
            lines.append("")
            lines.append(f"cover: {json.dumps(cover_rel_path, ensure_ascii=False)}")
        return "\n".join(lines) + "\n"

    def _stop_asset_audio(self):
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except RuntimeError:
            pass
        try:
            ctypes.windll.winmm.mciSendStringW("close sgm_asset_audio", None, 0, None)
        except Exception:
            pass
        if self.asset_viewer_audio_temp_path:
            try:
                Path(self.asset_viewer_audio_temp_path).unlink(missing_ok=True)
            except OSError:
                pass
        self.asset_viewer_audio_temp_path = None

    def _extract_asset_preview_image(self, data):
        if Image is None or ImageTk is None:
            return None
        pil_image = None
        try:
            if hasattr(data, "image"):
                pil_image = data.image
        except Exception:
            pil_image = None
        if pil_image is None:
            return None
        if not isinstance(pil_image, Image.Image):
            return None
        preview = pil_image.copy()
        preview.thumbnail((440, 300), Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(preview)

    def _extract_asset_audio_sample(self, data):
        samples = getattr(data, "samples", None)
        if not samples:
            return None
        try:
            sample_name, sample_bytes = next(iter(samples.items()))
        except Exception:
            return None
        return sample_name, sample_bytes

    def _get_lmr_unity_fallback_version(self) -> str:
        fallback_version = LMR_FALLBACK_UNITY_VERSION
        if UnityPy is None or not LMR_RESOURCES_ASSETS_PATH.exists():
            return fallback_version
        try:
            env = UnityPy.load(str(LMR_RESOURCES_ASSETS_PATH))
            for asset_file in env.files.values():
                unity_version = str(getattr(asset_file, "unity_version", "") or "").strip()
                if unity_version:
                    return unity_version
        except Exception:
            pass
        return fallback_version

    def _get_lmr_bundle_paths(self):
        if UnityPy is None:
            raise RuntimeError("UnityPy is not installed.")
        if not LMR_BUNDLES_DIR.exists():
            raise FileNotFoundError("LMR bundle directory was not found.")
        bundle_paths = sorted(LMR_BUNDLES_DIR.glob("*.bundle"))
        if not bundle_paths:
            raise FileNotFoundError("No LMR bundle files were found.")
        return bundle_paths

    def _load_lmr_asset_entries(self):
        if UnityPy is None:
            raise RuntimeError("UnityPy is not installed.")
        bundle_paths = self._get_lmr_bundle_paths()
        if hasattr(UnityPy, "config"):
            try:
                UnityPy.config.FALLBACK_UNITY_VERSION = self._get_lmr_unity_fallback_version()
            except Exception:
                pass
        allowed_types = {"Texture2D", "Sprite", "AudioClip"}
        entries = []
        for bundle_path in bundle_paths:
            try:
                env = UnityPy.load(str(bundle_path))
            except Exception:
                continue
            for index, obj in enumerate(env.objects):
                try:
                    data = obj.read()
                except Exception:
                    continue

                asset_type = str(getattr(obj.type, "name", obj.type))
                if asset_type not in allowed_types:
                    continue

                raw_name = (getattr(data, "m_Name", "") or getattr(data, "name", "") or "").strip()
                image_preview = self._extract_asset_preview_image(data) if asset_type in {"Texture2D", "Sprite"} else None
                audio_sample = self._extract_asset_audio_sample(data) if asset_type == "AudioClip" else None

                if image_preview is None and audio_sample is None and not raw_name:
                    continue

                technical_name = raw_name or f"{bundle_path.stem}:{asset_type.lower()}_{index}"
                entries.append(
                    {
                        "technical_name": technical_name,
                        "file_name": bundle_path.name,
                        "type": asset_type,
                        "object_id": obj.path_id,
                        "preview_image": image_preview,
                        "audio_sample": audio_sample,
                    }
                )
        entries.sort(key=lambda item: (item["type"], item["technical_name"].lower()))
        return entries

    def _filter_asset_viewer_entries(self, *_args):
        if self.asset_viewer_tree is None:
            return
        search = (self.asset_viewer_search_var.get().strip().lower() if self.asset_viewer_search_var is not None else "")
        type_filter = self.asset_viewer_type_var.get().strip().lower() if self.asset_viewer_type_var is not None else "all"
        self.asset_viewer_tree.delete(*self.asset_viewer_tree.get_children())
        self.asset_viewer_filtered_entries = []
        for entry in self.asset_viewer_entries:
            haystack = f'{entry["technical_name"]} {entry["file_name"]} {entry["type"]}'.lower()
            if search and search not in haystack:
                continue
            entry_type = entry["type"]
            if type_filter == "images" and entry_type not in {"Texture2D", "Sprite"}:
                continue
            if type_filter == "audio" and entry_type != "AudioClip":
                continue
            item_id = self.asset_viewer_tree.insert("", "end", values=(entry["technical_name"], entry["file_name"], entry["type"]))
            self.asset_viewer_tree.set(item_id, "object_id", str(entry["object_id"]))
            self.asset_viewer_filtered_entries.append((item_id, entry))

    def _play_asset_audio_sample(self, sample_name, sample_bytes):
        self._stop_asset_audio()
        suffix = Path(sample_name).suffix or ".wav"
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temp_file.write(sample_bytes)
        temp_file.close()
        self.asset_viewer_audio_temp_path = temp_file.name
        if suffix.lower() == ".wav":
            winsound.PlaySound(temp_file.name, winsound.SND_ASYNC | winsound.SND_FILENAME)
            return
        alias = "sgm_asset_audio"
        ctypes.windll.winmm.mciSendStringW(f'open "{temp_file.name}" type mpegvideo alias {alias}', None, 0, None)
        ctypes.windll.winmm.mciSendStringW(f"play {alias}", None, 0, None)

    def _show_selected_asset_preview(self, _event=None):
        if self.asset_viewer_tree is None or self.asset_viewer_preview_label is None:
            return
        selection = self.asset_viewer_tree.selection()
        if not selection:
            return
        selected_id = selection[0]
        entry = next((entry for item_id, entry in self.asset_viewer_filtered_entries if item_id == selected_id), None)
        if entry is None:
            return
        self._stop_asset_audio()
        preview_text = f'Tech: {entry["technical_name"]}\nBundle: {entry["file_name"]}\nType: {entry["type"]}'
        if entry["preview_image"] is not None:
            self.asset_viewer_preview_image = entry["preview_image"]
            self.asset_viewer_preview_label.configure(image=self.asset_viewer_preview_image, text=preview_text, compound="top")
        else:
            self.asset_viewer_preview_image = None
            self.asset_viewer_preview_label.configure(image="", text=preview_text)
        if self.asset_viewer_audio_info_var is not None:
            if entry["audio_sample"] is not None:
                sample_name, sample_bytes = entry["audio_sample"]
                self.asset_viewer_audio_info_var.set(f"Audio: {sample_name} ({len(sample_bytes)} bytes)")
            else:
                self.asset_viewer_audio_info_var.set("Audio: not available")

    def _play_selected_asset_audio(self):
        if self.asset_viewer_tree is None:
            return
        selection = self.asset_viewer_tree.selection()
        if not selection:
            return
        selected_id = selection[0]
        entry = next((entry for item_id, entry in self.asset_viewer_filtered_entries if item_id == selected_id), None)
        if entry is None or entry["audio_sample"] is None:
            return
        sample_name, sample_bytes = entry["audio_sample"]
        self._play_asset_audio_sample(sample_name, sample_bytes)

    def close_asset_viewer_window(self):
        self._stop_asset_audio()
        if self.asset_viewer_window is not None and self.asset_viewer_window.winfo_exists():
            try:
                self.asset_viewer_window.grab_release()
            except tk.TclError:
                pass
            self.asset_viewer_window.destroy()
        self.asset_viewer_window = None
        self.asset_viewer_tree = None
        self.asset_viewer_entries = []
        self.asset_viewer_filtered_entries = []
        self.asset_viewer_bundle_paths = []
        self.asset_viewer_bundle_var = None
        self.asset_viewer_type_var = None
        self.asset_viewer_preview_label = None
        self.asset_viewer_preview_image = None
        self.asset_viewer_audio_info_var = None
        self.asset_viewer_search_var = None
        self._focus_editor_widget()

    def open_lmr_asset_viewer(self):
        if self.asset_viewer_window is not None and self.asset_viewer_window.winfo_exists():
            self.asset_viewer_window.lift()
            self.asset_viewer_window.focus_force()
            return
        try:
            entries = self._load_lmr_asset_entries()
        except Exception as error:
            messagebox.showwarning("Bundle Viewer", str(error), parent=self.root)
            return

        width = 1120
        height = 720
        window = tk.Toplevel(self.root)
        window.transient(self.root)
        window.configure(bg=TRANSPARENT_COLOR)
        window.overrideredirect(True)
        try:
            window.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)
        except tk.TclError:
            pass
        window.geometry(f"{width}x{height}+{self.root.winfo_x() + 140}+{self.root.winfo_y() + 80}")
        canvas = tk.Canvas(window, width=width, height=height, bg=TRANSPARENT_COLOR, highlightthickness=0, bd=0)
        canvas.pack()
        self._draw_window_frame(canvas, width, height)
        canvas.create_text(width // 2, 16, text="LMR Bundle Viewer", anchor="n", fill="#f0f0f0", font=("Cascadia Mono", 12, "bold"))
        drag_zone = canvas.create_rectangle(18, 10, width - 18, 42, outline="", fill="")

        drag_state = {"x": 0, "y": 0}
        def start_drag(event):
            drag_state["x"] = event.x_root - window.winfo_x()
            drag_state["y"] = event.y_root - window.winfo_y()
        def drag_window(event):
            window.geometry(f"+{event.x_root - drag_state['x']}+{event.y_root - drag_state['y']}")
        canvas.tag_bind(drag_zone, "<ButtonPress-1>", start_drag)
        canvas.tag_bind(drag_zone, "<B1-Motion>", drag_window)

        self.asset_viewer_window = window
        self.asset_viewer_entries = entries
        self.asset_viewer_filtered_entries = []
        self.asset_viewer_bundle_paths = []
        self.asset_viewer_bundle_var = None
        self.asset_viewer_search_var = tk.StringVar()
        self.asset_viewer_type_var = tk.StringVar(value="All")
        self.asset_viewer_search_var.trace_add("write", self._filter_asset_viewer_entries)
        self.asset_viewer_type_var.trace_add("write", self._filter_asset_viewer_entries)
        self.asset_viewer_audio_info_var = tk.StringVar(value="Audio: not available")

        search_entry = tk.Entry(window, textvariable=self.asset_viewer_search_var, font=("Cascadia Mono", 9), bg="#101010", fg="#f0f0f0", insertbackground="#56f4ee", bd=0, highlightthickness=1, highlightbackground="#1d1d1d")
        canvas.create_window(24, 54, anchor="nw", window=search_entry, width=430, height=24)

        type_combo = ttk.Combobox(window, textvariable=self.asset_viewer_type_var, values=["All", "Images", "Audio"], state="readonly")
        canvas.create_window(470, 54, anchor="nw", window=type_combo, width=120, height=24)

        self._create_composite_button(window, canvas, width - 118, 52, "Close", 56, 24, self.close_asset_viewer_window)
        self._create_composite_button(window, canvas, 736, 644, "Play", 56, 24, self._play_selected_asset_audio)
        self._create_composite_button(window, canvas, 828, 644, "Stop", 56, 24, self._stop_asset_audio)

        tree = ttk.Treeview(window, columns=("technical_name", "file_name", "type", "object_id"), show="headings", selectmode="browse")
        tree.heading("technical_name", text="Technical Name")
        tree.heading("file_name", text="Bundle")
        tree.heading("type", text="Type")
        tree.column("technical_name", width=360, anchor="w")
        tree.column("file_name", width=180, anchor="w")
        tree.column("type", width=110, anchor="w")
        tree.column("object_id", width=0, stretch=False)
        tree["displaycolumns"] = ("technical_name", "file_name", "type")
        tree.bind("<<TreeviewSelect>>", self._show_selected_asset_preview)
        canvas.create_window(24, 88, anchor="nw", window=tree, width=660, height=610)
        self.asset_viewer_tree = tree

        preview_frame = tk.Frame(window, bg="#101010", bd=0, highlightthickness=1, highlightbackground="#1d1d1d")
        canvas.create_window(708, 88, anchor="nw", window=preview_frame, width=388, height=540)
        self.asset_viewer_preview_label = tk.Label(preview_frame, bg="#101010", fg="#f0f0f0", font=("Cascadia Mono", 9, "bold"), justify="left", anchor="n", compound="top", wraplength=360)
        self.asset_viewer_preview_label.place(x=12, y=12, width=364, height=504)
        audio_info = tk.Label(window, textvariable=self.asset_viewer_audio_info_var, bg=TRANSPARENT_COLOR, fg="#56f4ee", font=("Cascadia Mono", 8, "bold"), anchor="w", justify="left")
        canvas.create_window(708, 612, anchor="nw", window=audio_info, width=320, height=20)

        self._filter_asset_viewer_entries()
        if tree.get_children():
            first_item = tree.get_children()[0]
            tree.selection_set(first_item)
            tree.focus(first_item)
            self._show_selected_asset_preview()

        window.bind("<Escape>", lambda _e: self.close_asset_viewer_window())
        window.deiconify()
        window.lift()
        window.focus_force()

    def _resolve_lmr_game_data_dir(self, selected_dir: Path) -> Path:
        candidates = []
        if selected_dir.name.endswith("_Data"):
            candidates.append(selected_dir)
        candidates.append(selected_dir / "Love, Money, Rock'n'Roll_Data")
        for child in selected_dir.glob("*_Data"):
            candidates.append(child)
        seen = set()
        for candidate in candidates:
            candidate = candidate.resolve()
            if candidate in seen:
                continue
            seen.add(candidate)
            bundle_dir = candidate / "StreamingAssets" / "aa" / "StandaloneWindows64"
            if bundle_dir.exists():
                return candidate
        raise FileNotFoundError("Could not find Love, Money, Rock'n'Roll_Data with bundle files in the selected folder.")

    def _get_unity_fallback_version_for_game_data(self, game_data_dir: Path) -> str:
        fallback_version = LMR_FALLBACK_UNITY_VERSION
        resources_assets_path = game_data_dir / "resources.assets"
        if UnityPy is None or not resources_assets_path.exists():
            return fallback_version
        try:
            env = UnityPy.load(str(resources_assets_path))
            for asset_file in env.files.values():
                unity_version = str(getattr(asset_file, "unity_version", "") or "").strip()
                if unity_version:
                    return unity_version
        except Exception:
            pass
        return fallback_version

    def _sanitize_export_file_name(self, name: str, fallback: str, extension: str) -> str:
        cleaned = re.sub(r'[^A-Za-z0-9._-]+', '_', (name or '').strip())
        cleaned = cleaned.strip('._')
        if not cleaned:
            cleaned = fallback
        if not cleaned.lower().endswith(extension.lower()):
            cleaned += extension
        return cleaned

    def _make_unique_path(self, path: Path) -> Path:
        if not path.exists():
            return path
        stem = path.stem
        suffix = path.suffix
        counter = 2
        while True:
            candidate = path.with_name(f"{stem}_{counter}{suffix}")
            if not candidate.exists():
                return candidate
            counter += 1

    def _save_unity_image_asset(self, data, output_path: Path) -> bool:
        if Image is None:
            return False
        try:
            pil_image = getattr(data, "image", None)
        except Exception:
            return False
        if not isinstance(pil_image, Image.Image):
            return False
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pil_image.save(output_path)
        return True

    def _save_unity_audio_asset(self, data, base_name: str, output_dir: Path, fallback_prefix: str) -> int:
        samples = getattr(data, "samples", None)
        if not samples:
            return 0
        output_dir.mkdir(parents=True, exist_ok=True)
        exported = 0
        for sample_name, sample_bytes in samples.items():
            suffix = Path(sample_name).suffix or ".wav"
            file_name = self._sanitize_export_file_name(Path(sample_name).stem, f"{fallback_prefix}_{exported}", suffix)
            target_path = self._make_unique_path(output_dir / file_name)
            target_path.write_bytes(sample_bytes)
            exported += 1
        return exported

    def _extract_lmr_bundles_worker(self, game_dir_str: str, output_dir_str: str, progress_queue):
        try:
            if UnityPy is None:
                raise RuntimeError("UnityPy is not installed.")
            game_data_dir = self._resolve_lmr_game_data_dir(Path(game_dir_str))
            bundle_dir = game_data_dir / "StreamingAssets" / "aa" / "StandaloneWindows64"
            bundle_paths = sorted(bundle_dir.glob("*.bundle"))
            if not bundle_paths:
                raise FileNotFoundError("No .bundle files were found in the selected game folder.")

            if hasattr(UnityPy, "config"):
                try:
                    UnityPy.config.FALLBACK_UNITY_VERSION = self._get_unity_fallback_version_for_game_data(game_data_dir)
                except Exception:
                    pass

            output_root = Path(output_dir_str)
            sprites_dir = output_root / "sprites"
            textures_dir = output_root / "textures"
            audio_dir = output_root / "audio"
            sprites_dir.mkdir(parents=True, exist_ok=True)
            textures_dir.mkdir(parents=True, exist_ok=True)
            audio_dir.mkdir(parents=True, exist_ok=True)

            counts = {"sprites": 0, "textures": 0, "audio": 0, "failed_bundles": 0}
            for index, bundle_path in enumerate(bundle_paths, start=1):
                progress_queue.put(("progress", f"[{index}/{len(bundle_paths)}] {bundle_path.name}"))
                try:
                    env = UnityPy.load(str(bundle_path))
                except Exception:
                    counts["failed_bundles"] += 1
                    continue

                for obj_index, obj in enumerate(env.objects):
                    try:
                        data = obj.read()
                    except Exception:
                        continue
                    asset_type = str(getattr(obj.type, "name", obj.type))
                    raw_name = (getattr(data, "m_Name", "") or getattr(data, "name", "") or "").strip()
                    base_name = raw_name or f"{bundle_path.stem}_{asset_type.lower()}_{obj.path_id or obj_index}"

                    if asset_type == "Sprite":
                        file_name = self._sanitize_export_file_name(base_name, f"sprite_{obj.path_id}", ".png")
                        target_path = self._make_unique_path(sprites_dir / file_name)
                        if self._save_unity_image_asset(data, target_path):
                            counts["sprites"] += 1
                    elif asset_type == "Texture2D":
                        file_name = self._sanitize_export_file_name(base_name, f"texture_{obj.path_id}", ".png")
                        target_path = self._make_unique_path(textures_dir / file_name)
                        if self._save_unity_image_asset(data, target_path):
                            counts["textures"] += 1
                    elif asset_type == "AudioClip":
                        counts["audio"] += self._save_unity_audio_asset(data, base_name, audio_dir, f"audio_{obj.path_id}")

            progress_queue.put(("done", counts, str(output_root)))
        except Exception as error:
            progress_queue.put(("error", str(error)))

    def _poll_lmr_bundle_extractor(self, progress_window, status_var, result_queue):
        try:
            while True:
                message = result_queue.get_nowait()
                kind = message[0]
                if kind == "progress":
                    status_var.set(message[1])
                elif kind == "done":
                    counts, output_root = message[1], message[2]
                    if progress_window.winfo_exists():
                        progress_window.destroy()
                    messagebox.showinfo(
                        "LMR Bundle Extractor",
                        f"Export completed.\\n\\nSprites: {counts['sprites']}\\nTextures: {counts['textures']}\\nAudio files: {counts['audio']}\\nFailed bundles: {counts['failed_bundles']}\\n\\nOutput: {output_root}",
                        parent=self.root,
                    )
                    self._focus_editor_widget()
                    return
                elif kind == "error":
                    if progress_window.winfo_exists():
                        progress_window.destroy()
                    messagebox.showwarning("LMR Bundle Extractor", message[1], parent=self.root)
                    self._focus_editor_widget()
                    return
        except queue.Empty:
            if progress_window.winfo_exists():
                progress_window.after(120, lambda: self._poll_lmr_bundle_extractor(progress_window, status_var, result_queue))

    def open_lmr_bundle_extractor(self):
        initial_game_dir = self.app_settings.get("default_lmr_game_dir") or str(LMR_GAME_DATA_DIR.parent)
        game_dir = filedialog.askdirectory(parent=self.root, title="Select LMR game folder", initialdir=initial_game_dir)
        if not game_dir:
            return
        output_dir = filedialog.askdirectory(parent=self.root, title="Select output folder", initialdir=str(Path(game_dir)))
        if not output_dir:
            return

        progress_window = tk.Toplevel(self.root)
        progress_window.transient(self.root)
        progress_window.title("LMR Bundle Extractor")
        progress_window.resizable(False, False)
        progress_window.geometry(f"420x120+{self.root.winfo_x() + 180}+{self.root.winfo_y() + 140}")
        progress_window.configure(bg="#111111")
        progress_window.protocol("WM_DELETE_WINDOW", progress_window.destroy)

        title_label = tk.Label(progress_window, text="Extracting bundle assets...", font=("Cascadia Mono", 11, "bold"), fg="#56f4ee", bg="#111111")
        title_label.pack(pady=(18, 10))
        status_var = tk.StringVar(value="Preparing...")
        status_label = tk.Label(progress_window, textvariable=status_var, font=("Cascadia Mono", 9), fg="#f0f0f0", bg="#111111", wraplength=380, justify="center")
        status_label.pack(padx=20)

        result_queue = queue.Queue()
        worker = threading.Thread(target=self._extract_lmr_bundles_worker, args=(game_dir, output_dir, result_queue), daemon=True)
        worker.start()
        progress_window.after(120, lambda: self._poll_lmr_bundle_extractor(progress_window, status_var, result_queue))

    def _get_lmr_resources_path(self) -> Path | None:
        if self._detect_project_type() != "lmr" or self.project_dir is None:
            return None
        return self.project_dir / "resources.yaml"

    def _read_lmr_resources_content(self) -> str:
        resources_path = self._get_lmr_resources_path()
        if resources_path is None:
            raise RuntimeError("LMR project is not open.")
        if resources_path.exists():
            return resources_path.read_text(encoding="utf-8")
        return "---\n"

    def _write_lmr_resources_content(self, content: str):
        resources_path = self._get_lmr_resources_path()
        if resources_path is None:
            raise RuntimeError("LMR project is not open.")
        resources_path.write_text(content.rstrip() + "\n", encoding="utf-8")
        updated = resources_path.read_text(encoding="utf-8")
        self.saved_file_snapshots[resources_path] = updated
        self.file_buffers[resources_path] = updated
        self.dirty_files.discard(resources_path)
        if self.current_file == resources_path and self.editor_text is not None:
            current_index = self.editor_text.index("insert")
            self._set_editor_content(updated)
            try:
                self.editor_text.mark_set("insert", current_index)
                self.editor_text.see(current_index)
            except tk.TclError:
                pass
            self._refresh_line_numbers(force=True)
            self._update_status(refresh_lines=False)
            self._request_render_file_tabs()
        self._reload_project_files()

    def _find_top_level_block_range(self, lines: list[str], block_name: str):
        header = f"{block_name}:"
        start = None
        for index, line in enumerate(lines):
            if line.strip() == header:
                start = index
                break
        if start is None:
            return None, None
        end = len(lines)
        for index in range(start + 1, len(lines)):
            line = lines[index]
            if line and not line.startswith(" "):
                end = index
                break
        return start, end

    def _upsert_lmr_named_entry(self, block_name: str, key: str, entry_lines: list[str]):
        content = self._read_lmr_resources_content()
        lines = content.splitlines()
        start, end = self._find_top_level_block_range(lines, block_name)
        if start is None:
            if lines and lines[-1].strip():
                lines.append("")
            lines.append(f"{block_name}:")
            start = len(lines) - 1
            end = len(lines)

        entry_start = None
        entry_end = None
        prefix = f"    {key}:"
        for index in range(start + 1, end):
            if lines[index].startswith(prefix):
                entry_start = index
                entry_end = end
                for inner in range(index + 1, end):
                    if lines[inner].startswith("    ") and not lines[inner].startswith("        "):
                        entry_end = inner
                        break
                break

        if entry_start is not None and entry_end is not None:
            lines[entry_start:entry_end] = entry_lines
        else:
            insert_at = end
            while insert_at > start + 1 and lines[insert_at - 1] == "":
                insert_at -= 1
            if insert_at > start + 1 and lines[insert_at - 1].strip():
                lines.insert(insert_at, "")
                insert_at += 1
            lines[insert_at:insert_at] = entry_lines

        self._write_lmr_resources_content("\n".join(lines))

    def _upsert_lmr_top_level_scalar(self, key: str, value_line: str):
        content = self._read_lmr_resources_content()
        lines = content.splitlines()
        replaced = False
        for index, line in enumerate(lines):
            if line.startswith(f"{key}:"):
                lines[index] = f"{key}: {value_line}"
                replaced = True
                break
        if not replaced:
            if lines and lines[-1].strip():
                lines.append("")
            lines.append(f"{key}: {value_line}")
        self._write_lmr_resources_content("\n".join(lines))

    def _get_lmr_scenario_ids(self) -> list[str]:
        try:
            content = self._read_lmr_resources_content()
        except Exception:
            return []
        lines = content.splitlines()
        start, end = self._find_top_level_block_range(lines, "scenarios")
        if start is None:
            return []
        ids = []
        for index in range(start + 1, end):
            line = lines[index]
            if line.startswith("    "):
                stripped = line.strip()
                if ":" in stripped:
                    ids.append(stripped.split(":", 1)[0].strip())
        return ids

    def _normalize_lmr_folder(self, value: str) -> str:
        cleaned = value.strip().replace("\\", "/").strip("/")
        cleaned = re.sub(r"[^A-Za-z0-9_./-]+", "_", cleaned)
        return cleaned

    def _copy_lmr_asset_into_project(self, source_path: Path, folder: str, rename_to: str | None = None):
        if self.project_dir is None:
            raise RuntimeError("Project is not open.")
        normalized_folder = self._normalize_lmr_folder(folder)
        target_dir = self.project_dir / normalized_folder if normalized_folder else self.project_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        stem = rename_to.strip() if rename_to else source_path.stem
        stem = re.sub(r"[^A-Za-z0-9_./-]+", "_", stem).strip("._")
        if not stem:
            stem = source_path.stem
        target_name = f"{stem}{source_path.suffix.lower()}"
        target_path = target_dir / target_name
        if target_path.resolve() != source_path.resolve():
            shutil.copy2(source_path, target_path)
        rel_path = target_path.relative_to(self.project_dir).as_posix()
        return rel_path, target_path

    def _update_preview_label_from_path(self, label_widget: tk.Label, image_path: str):
        if Image is None or ImageTk is None:
            label_widget.configure(text="Preview unavailable", image="")
            return
        if not image_path or not Path(image_path).exists():
            label_widget.configure(text="Preview unavailable", image="")
            label_widget.image = None
            return
        try:
            preview = Image.open(image_path)
            preview.thumbnail((320, 180), Image.Resampling.LANCZOS)
            tk_image = ImageTk.PhotoImage(preview)
        except Exception:
            label_widget.configure(text="Preview unavailable", image="")
            label_widget.image = None
            return
        label_widget.configure(text="", image=tk_image)
        label_widget.image = tk_image

    def _open_lmr_basic_dialog(self, title: str, width: int = 640, height: int = 420):
        window = tk.Toplevel(self.root)
        window.transient(self.root)
        window.title(title)
        window.geometry(f"{width}x{height}+{self.root.winfo_x() + 140}+{self.root.winfo_y() + 100}")
        window.configure(bg="#111111")
        window.resizable(False, False)
        return window

    def _show_lmr_warning(self, title: str, text: str, parent):
        messagebox.showwarning(title, text, parent=parent)

    def _ask_open_file(self, parent, title: str, filetypes):
        return filedialog.askopenfilename(parent=parent, title=title, filetypes=filetypes)

    def add_lmr_backdrop_bg(self):
        self._open_lmr_visual_resource_dialog(section_name="backdrop_bg", title="Add backdrop_bg", allow_animation=False, allow_prefab=True)

    def add_lmr_bg(self):
        self._open_lmr_visual_resource_dialog(section_name="bg", title="Add bg", allow_animation=True, allow_prefab=True)

    def add_lmr_cg(self):
        self._open_lmr_visual_resource_dialog(section_name="cg", title="Add cg", allow_animation=True, allow_prefab=True)

    def add_lmr_sound(self):
        if self._detect_project_type() != "lmr":
            return
        window = self._open_lmr_basic_dialog("Add sound", width=620, height=260)
        labels = [
            ("Technical Name", 20, 24),
            ("Asset Name", 20, 84),
            ("Folder", 320, 84),
            ("Source File", 20, 144),
        ]
        for text, x, y in labels:
            tk.Label(window, text=text, bg="#111111", fg="#f0f0f0", font=("Cascadia Mono", 9, "bold")).place(x=x, y=y)
        technical_var = tk.StringVar()
        asset_name_var = tk.StringVar()
        folder_var = tk.StringVar(value="sound")
        file_var = tk.StringVar()
        tk.Entry(window, textvariable=technical_var, bg="#1a1a1a", fg="#f0f0f0", insertbackground="#56f4ee").place(x=20, y=46, width=260, height=24)
        tk.Entry(window, textvariable=asset_name_var, bg="#1a1a1a", fg="#f0f0f0", insertbackground="#56f4ee").place(x=20, y=106, width=260, height=24)
        tk.Entry(window, textvariable=folder_var, bg="#1a1a1a", fg="#f0f0f0", insertbackground="#56f4ee").place(x=320, y=106, width=180, height=24)
        tk.Entry(window, textvariable=file_var, bg="#1a1a1a", fg="#f0f0f0", insertbackground="#56f4ee").place(x=20, y=166, width=480, height=24)
        tk.Button(window, text="Browse", command=lambda: file_var.set(self._ask_open_file(window, "Select sound file", [("Audio", "*.ogg *.wav *.mp3"), ("All files", "*.*")]))).place(x=514, y=164, width=80, height=28)

        def submit():
            source = Path(file_var.get().strip())
            key = self._slugify_project_id(technical_var.get().strip())
            if not key:
                self._show_lmr_warning("Invalid Name", "Enter a valid technical name.", window)
                return
            if not source.exists():
                self._show_lmr_warning("Missing File", "Select a valid sound file.", window)
                return
            rel_path, _ = self._copy_lmr_asset_into_project(source, folder_var.get(), asset_name_var.get().strip() or None)
            self._upsert_lmr_named_entry("sound", key, [f"    {key}: {rel_path}"])
            window.destroy()

        tk.Button(window, text="Add", command=submit).place(x=514, y=218, width=80, height=28)
        tk.Button(window, text="Cancel", command=window.destroy).place(x=424, y=218, width=80, height=28)
        window.grab_set()
        window.focus_force()

    def add_lmr_backdrop_text(self):
        if self._detect_project_type() != "lmr":
            return
        window = self._open_lmr_basic_dialog("Add backdrop_text", width=620, height=290)
        tk.Label(window, text="Technical Name", bg="#111111", fg="#f0f0f0", font=("Cascadia Mono", 9, "bold")).place(x=20, y=24)
        tk.Label(window, text="Locale", bg="#111111", fg="#f0f0f0", font=("Cascadia Mono", 9, "bold")).place(x=320, y=24)
        tk.Label(window, text="Text", bg="#111111", fg="#f0f0f0", font=("Cascadia Mono", 9, "bold")).place(x=20, y=84)
        technical_var = tk.StringVar()
        locale_var = tk.StringVar(value="ru")
        text_var = tk.StringVar()
        tk.Entry(window, textvariable=technical_var, bg="#1a1a1a", fg="#f0f0f0", insertbackground="#56f4ee").place(x=20, y=46, width=260, height=24)
        ttk.Combobox(window, textvariable=locale_var, values=["ru", "en", "ja", "zh"], state="readonly").place(x=320, y=46, width=120, height=24)
        tk.Entry(window, textvariable=text_var, bg="#1a1a1a", fg="#f0f0f0", insertbackground="#56f4ee").place(x=20, y=106, width=574, height=24)

        def submit():
            key = self._slugify_project_id(technical_var.get().strip())
            if not key:
                self._show_lmr_warning("Invalid Name", "Enter a valid technical name.", window)
                return
            value = text_var.get().strip()
            if not value:
                self._show_lmr_warning("Missing Text", "Enter text for backdrop_text.", window)
                return
            entry_lines = [
                f"    {key}:",
                f"        {locale_var.get().strip()}: {json.dumps(value, ensure_ascii=False)}",
            ]
            self._upsert_lmr_named_entry("backdrop_text", key, entry_lines)
            window.destroy()

        tk.Button(window, text="Add", command=submit).place(x=514, y=248, width=80, height=28)
        tk.Button(window, text="Cancel", command=window.destroy).place(x=424, y=248, width=80, height=28)
        window.grab_set()
        window.focus_force()

    def add_lmr_variable(self):
        if self._detect_project_type() != "lmr":
            return
        window = self._open_lmr_basic_dialog("Add variable", width=620, height=280)
        tk.Label(window, text="Technical Name", bg="#111111", fg="#f0f0f0", font=("Cascadia Mono", 9, "bold")).place(x=20, y=24)
        tk.Label(window, text="Value Type", bg="#111111", fg="#f0f0f0", font=("Cascadia Mono", 9, "bold")).place(x=320, y=24)
        tk.Label(window, text="Value", bg="#111111", fg="#f0f0f0", font=("Cascadia Mono", 9, "bold")).place(x=20, y=84)
        technical_var = tk.StringVar()
        value_type_var = tk.StringVar(value="number")
        value_var = tk.StringVar(value="0")
        tk.Entry(window, textvariable=technical_var, bg="#1a1a1a", fg="#f0f0f0", insertbackground="#56f4ee").place(x=20, y=46, width=260, height=24)
        ttk.Combobox(window, textvariable=value_type_var, values=["number", "text", "boolean", "expression"], state="readonly").place(x=320, y=46, width=140, height=24)
        tk.Entry(window, textvariable=value_var, bg="#1a1a1a", fg="#f0f0f0", insertbackground="#56f4ee").place(x=20, y=106, width=574, height=24)

        def submit():
            key = self._slugify_project_id(technical_var.get().strip())
            if not key:
                self._show_lmr_warning("Invalid Name", "Enter a valid technical name.", window)
                return
            raw_value = value_var.get().strip()
            if value_type_var.get() == "text":
                rendered = json.dumps(raw_value, ensure_ascii=False)
            elif value_type_var.get() == "boolean":
                rendered = "true" if raw_value.lower() in {"1", "true", "yes", "on"} else "false"
            else:
                rendered = raw_value or "0"
            self._upsert_lmr_named_entry("variables", key, [f"    {key}: {rendered}"])
            window.destroy()

        tk.Button(window, text="Add", command=submit).place(x=514, y=238, width=80, height=28)
        tk.Button(window, text="Cancel", command=window.destroy).place(x=424, y=238, width=80, height=28)
        window.grab_set()
        window.focus_force()

    def add_lmr_catalogs(self):
        if self._detect_project_type() != "lmr":
            return
        window = self._open_lmr_basic_dialog("Add catalogs", width=700, height=360)
        tk.Label(window, text="Catalog Name", bg="#111111", fg="#f0f0f0", font=("Cascadia Mono", 9, "bold")).place(x=20, y=24)
        tk.Label(window, text="Mode", bg="#111111", fg="#f0f0f0", font=("Cascadia Mono", 9, "bold")).place(x=300, y=24)
        name_var = tk.StringVar(value="bundle")
        mode_var = tk.StringVar(value="single")
        path_var = tk.StringVar(value="catalogs/bundle/catalog.json")
        platform_vars = {platform: tk.StringVar() for platform in ("windows", "linux", "macos", "android", "ios")}
        tk.Entry(window, textvariable=name_var, bg="#1a1a1a", fg="#f0f0f0", insertbackground="#56f4ee").place(x=20, y=46, width=240, height=24)
        ttk.Combobox(window, textvariable=mode_var, values=["single", "platforms"], state="readonly").place(x=300, y=46, width=120, height=24)
        single_label = tk.Label(window, text="Catalog Path", bg="#111111", fg="#f0f0f0", font=("Cascadia Mono", 9, "bold"))
        single_entry = tk.Entry(window, textvariable=path_var, bg="#1a1a1a", fg="#f0f0f0", insertbackground="#56f4ee")
        single_label.place(x=20, y=92)
        single_entry.place(x=20, y=114, width=640, height=24)
        platform_widgets = []
        start_y = 92
        for index, platform in enumerate(("windows", "linux", "macos", "android", "ios")):
            label = tk.Label(window, text=platform, bg="#111111", fg="#f0f0f0", font=("Cascadia Mono", 9, "bold"))
            entry = tk.Entry(window, textvariable=platform_vars[platform], bg="#1a1a1a", fg="#f0f0f0", insertbackground="#56f4ee")
            platform_widgets.append((label, entry, start_y + index * 44))

        def update_form(*_args):
            is_single = mode_var.get() == "single"
            if is_single:
                single_label.place(x=20, y=92)
                single_entry.place(x=20, y=114, width=640, height=24)
            else:
                single_label.place_forget()
                single_entry.place_forget()
            for label, entry, y in platform_widgets:
                if is_single:
                    label.place_forget()
                    entry.place_forget()
                else:
                    label.place(x=20, y=y)
                    entry.place(x=120, y=y, width=540, height=24)

        mode_var.trace_add("write", update_form)

        def submit():
            key = self._slugify_project_id(name_var.get().strip())
            if not key:
                self._show_lmr_warning("Invalid Name", "Enter a valid catalog name.", window)
                return
            if mode_var.get() == "single":
                value = path_var.get().strip()
                if not value:
                    self._show_lmr_warning("Missing Path", "Enter the catalog json path.", window)
                    return
                entry_lines = [f"    {key}: {value}"]
            else:
                lines = [f"    {key}:"]
                used = False
                for platform, var in platform_vars.items():
                    value = var.get().strip()
                    if value:
                        lines.append(f"        {platform}: {value}")
                        used = True
                if not used:
                    self._show_lmr_warning("Missing Paths", "Fill at least one platform path.", window)
                    return
                entry_lines = lines
            self._upsert_lmr_named_entry("catalogs", key, entry_lines)
            window.destroy()

        tk.Button(window, text="Add", command=submit).place(x=610, y=320, width=70, height=28)
        tk.Button(window, text="Cancel", command=window.destroy).place(x=530, y=320, width=70, height=28)
        update_form()
        window.grab_set()
        window.focus_force()

    def add_lmr_colors(self):
        self._open_lmr_color_value_dialog("colors", "Add colors", label_name="Color Name")

    def add_lmr_spritecolor(self):
        self._open_lmr_color_value_dialog("spritecolor", "Add overlay color", label_name="Overlay Name")

    def _open_lmr_color_value_dialog(self, section_name: str, title: str, label_name: str):
        if self._detect_project_type() != "lmr":
            return
        window = self._open_lmr_basic_dialog(title, width=520, height=220)
        tk.Label(window, text=label_name, bg="#111111", fg="#f0f0f0", font=("Cascadia Mono", 9, "bold")).place(x=20, y=24)
        tk.Label(window, text="Color Value", bg="#111111", fg="#f0f0f0", font=("Cascadia Mono", 9, "bold")).place(x=20, y=84)
        name_var = tk.StringVar()
        value_var = tk.StringVar(value="#56F4EE")
        tk.Entry(window, textvariable=name_var, bg="#1a1a1a", fg="#f0f0f0", insertbackground="#56f4ee").place(x=20, y=46, width=240, height=24)
        tk.Entry(window, textvariable=value_var, bg="#1a1a1a", fg="#f0f0f0", insertbackground="#56f4ee").place(x=20, y=106, width=240, height=24)

        def submit():
            key = self._slugify_project_id(name_var.get().strip())
            if not key:
                self._show_lmr_warning("Invalid Name", "Enter a valid name.", window)
                return
            value = value_var.get().strip()
            if not value:
                self._show_lmr_warning("Missing Color", "Enter a color value.", window)
                return
            self._upsert_lmr_named_entry(section_name, key, [f"    {key}: {json.dumps(value, ensure_ascii=False)}"])
            window.destroy()

        tk.Button(window, text="Add", command=submit).place(x=424, y=176, width=70, height=28)
        tk.Button(window, text="Cancel", command=window.destroy).place(x=344, y=176, width=70, height=28)
        window.grab_set()
        window.focus_force()

    def add_lmr_help(self):
        self._open_lmr_language_pair_dialog("help", "Add help", default_key="credits")

    def add_lmr_notes(self):
        self._open_lmr_language_pair_dialog("notes", "Add notes")

    def _open_lmr_language_pair_dialog(self, section_name: str, title: str, default_key: str = ""):
        if self._detect_project_type() != "lmr":
            return
        window = self._open_lmr_basic_dialog(title, width=680, height=300)
        tk.Label(window, text="Technical Name", bg="#111111", fg="#f0f0f0", font=("Cascadia Mono", 9, "bold")).place(x=20, y=24)
        tk.Label(window, text="RU Text", bg="#111111", fg="#f0f0f0", font=("Cascadia Mono", 9, "bold")).place(x=20, y=84)
        tk.Label(window, text="EN Text", bg="#111111", fg="#f0f0f0", font=("Cascadia Mono", 9, "bold")).place(x=20, y=164)
        key_var = tk.StringVar(value=default_key)
        ru_var = tk.StringVar()
        en_var = tk.StringVar()
        tk.Entry(window, textvariable=key_var, bg="#1a1a1a", fg="#f0f0f0", insertbackground="#56f4ee").place(x=20, y=46, width=280, height=24)
        tk.Entry(window, textvariable=ru_var, bg="#1a1a1a", fg="#f0f0f0", insertbackground="#56f4ee").place(x=20, y=106, width=620, height=24)
        tk.Entry(window, textvariable=en_var, bg="#1a1a1a", fg="#f0f0f0", insertbackground="#56f4ee").place(x=20, y=186, width=620, height=24)

        def submit():
            key = self._slugify_project_id(key_var.get().strip())
            if not key:
                self._show_lmr_warning("Invalid Name", "Enter a valid technical name.", window)
                return
            entry_lines = [f"    {key}:"]
            if ru_var.get().strip():
                entry_lines.append(f"        ru: {json.dumps(ru_var.get().strip(), ensure_ascii=False)}")
            if en_var.get().strip():
                entry_lines.append(f"        en: {json.dumps(en_var.get().strip(), ensure_ascii=False)}")
            if len(entry_lines) == 1:
                self._show_lmr_warning("Missing Text", "Enter at least one localized string.", window)
                return
            self._upsert_lmr_named_entry(section_name, key, entry_lines)
            window.destroy()

        tk.Button(window, text="Add", command=submit).place(x=570, y=256, width=70, height=28)
        tk.Button(window, text="Cancel", command=window.destroy).place(x=490, y=256, width=70, height=28)
        window.grab_set()
        window.focus_force()

    def add_lmr_positions(self):
        self._open_lmr_xy_dialog("positions", "Add positions", labels=("X", "Y"), defaults=("0", "0"))

    def add_lmr_sizes(self):
        self._open_lmr_xy_dialog("sizes", "Add sizes", labels=("X", "Y"), defaults=("1.0", "1.0"))

    def _open_lmr_xy_dialog(self, section_name: str, title: str, labels=("X", "Y"), defaults=("0", "0")):
        if self._detect_project_type() != "lmr":
            return
        window = self._open_lmr_basic_dialog(title, width=540, height=260)
        tk.Label(window, text="Technical Name", bg="#111111", fg="#f0f0f0", font=("Cascadia Mono", 9, "bold")).place(x=20, y=24)
        tk.Label(window, text=labels[0], bg="#111111", fg="#f0f0f0", font=("Cascadia Mono", 9, "bold")).place(x=20, y=84)
        tk.Label(window, text=labels[1], bg="#111111", fg="#f0f0f0", font=("Cascadia Mono", 9, "bold")).place(x=220, y=84)
        key_var = tk.StringVar()
        x_var = tk.StringVar(value=defaults[0])
        y_var = tk.StringVar(value=defaults[1])
        tk.Entry(window, textvariable=key_var, bg="#1a1a1a", fg="#f0f0f0", insertbackground="#56f4ee").place(x=20, y=46, width=260, height=24)
        tk.Entry(window, textvariable=x_var, bg="#1a1a1a", fg="#f0f0f0", insertbackground="#56f4ee").place(x=20, y=106, width=160, height=24)
        tk.Entry(window, textvariable=y_var, bg="#1a1a1a", fg="#f0f0f0", insertbackground="#56f4ee").place(x=220, y=106, width=160, height=24)

        def submit():
            key = self._slugify_project_id(key_var.get().strip())
            if not key:
                self._show_lmr_warning("Invalid Name", "Enter a valid technical name.", window)
                return
            self._upsert_lmr_named_entry(section_name, key, [
                f"    {key}:",
                f"        x: {x_var.get().strip() or defaults[0]}",
                f"        y: {y_var.get().strip() or defaults[1]}",
            ])
            window.destroy()

        tk.Button(window, text="Add", command=submit).place(x=444, y=216, width=70, height=28)
        tk.Button(window, text="Cancel", command=window.destroy).place(x=364, y=216, width=70, height=28)
        window.grab_set()
        window.focus_force()

    def add_lmr_transition(self):
        if self._detect_project_type() != "lmr":
            return
        window = self._open_lmr_basic_dialog("Add transition", width=640, height=320)
        tk.Label(window, text="Technical Name", bg="#111111", fg="#f0f0f0", font=("Cascadia Mono", 9, "bold")).place(x=20, y=24)
        tk.Label(window, text="Preset", bg="#111111", fg="#f0f0f0", font=("Cascadia Mono", 9, "bold")).place(x=20, y=84)
        tk.Label(window, text="Duration", bg="#111111", fg="#f0f0f0", font=("Cascadia Mono", 9, "bold")).place(x=220, y=84)
        tk.Label(window, text="Condition", bg="#111111", fg="#f0f0f0", font=("Cascadia Mono", 9, "bold")).place(x=20, y=144)
        key_var = tk.StringVar()
        preset_var = tk.StringVar(value="flash")
        duration_var = tk.StringVar(value="0.2")
        condition_var = tk.StringVar()
        tk.Entry(window, textvariable=key_var, bg="#1a1a1a", fg="#f0f0f0", insertbackground="#56f4ee").place(x=20, y=46, width=260, height=24)
        ttk.Combobox(window, textvariable=preset_var, values=["flash", "dissolve", "dissolve2", "fade", "wipeleft", "wiperight"], state="readonly").place(x=20, y=106, width=160, height=24)
        tk.Entry(window, textvariable=duration_var, bg="#1a1a1a", fg="#f0f0f0", insertbackground="#56f4ee").place(x=220, y=106, width=120, height=24)
        tk.Entry(window, textvariable=condition_var, bg="#1a1a1a", fg="#f0f0f0", insertbackground="#56f4ee").place(x=20, y=166, width=600, height=24)

        def submit():
            key = self._slugify_project_id(key_var.get().strip())
            if not key:
                self._show_lmr_warning("Invalid Name", "Enter a valid technical name.", window)
                return
            entry_lines = [
                f"    {key}:",
                f"        preset: {preset_var.get().strip() or 'flash'}",
                f"        duration: {duration_var.get().strip() or '0.2'}",
            ]
            if condition_var.get().strip():
                entry_lines.append(f"        condition: {json.dumps(condition_var.get().strip(), ensure_ascii=False)}")
            self._upsert_lmr_named_entry("transitions", key, entry_lines)
            window.destroy()

        tk.Button(window, text="Add", command=submit).place(x=550, y=276, width=70, height=28)
        tk.Button(window, text="Cancel", command=window.destroy).place(x=470, y=276, width=70, height=28)
        window.grab_set()
        window.focus_force()

    def add_lmr_entry_point(self):
        if self._detect_project_type() != "lmr":
            return
        scenario_ids = self._get_lmr_scenario_ids()
        if not scenario_ids:
            messagebox.showwarning("entryPoint", "No scenario technical names were found in resources.yaml.", parent=self.root)
            return
        window = self._open_lmr_basic_dialog("Add entryPoint", width=480, height=180)
        tk.Label(window, text="Scenario ID", bg="#111111", fg="#f0f0f0", font=("Cascadia Mono", 9, "bold")).place(x=20, y=24)
        scenario_var = tk.StringVar(value=scenario_ids[0])
        ttk.Combobox(window, textvariable=scenario_var, values=scenario_ids, state="readonly").place(x=20, y=46, width=300, height=24)

        def submit():
            value = scenario_var.get().strip()
            if not value:
                self._show_lmr_warning("Missing Scenario", "Choose a scenario ID.", window)
                return
            self._upsert_lmr_top_level_scalar("entryPoint", value)
            window.destroy()

        tk.Button(window, text="Add", command=submit).place(x=384, y=136, width=80, height=28)
        tk.Button(window, text="Cancel", command=window.destroy).place(x=294, y=136, width=80, height=28)
        window.grab_set()
        window.focus_force()

    def _open_lmr_visual_resource_dialog(self, section_name: str, title: str, allow_animation: bool, allow_prefab: bool):
        if self._detect_project_type() != "lmr":
            return
        window = self._open_lmr_basic_dialog(title, width=760, height=520 if allow_animation else 450)
        tech_var = tk.StringVar()
        asset_name_var = tk.StringVar()
        folder_var = tk.StringVar(value=section_name)
        mode_var = tk.StringVar(value="image")
        animated_var = tk.BooleanVar(value=False)
        static_var = tk.StringVar()
        anim_var = tk.StringVar()
        preview_label = tk.Label(window, text="Preview unavailable", bg="#161616", fg="#7a8481")
        preview_label.place(x=410, y=44, width=320, height=180)

        tk.Label(window, text="Technical Name", bg="#111111", fg="#f0f0f0", font=("Cascadia Mono", 9, "bold")).place(x=20, y=24)
        tk.Entry(window, textvariable=tech_var, bg="#1a1a1a", fg="#f0f0f0", insertbackground="#56f4ee").place(x=20, y=46, width=240, height=24)
        tk.Label(window, text="Asset Name", bg="#111111", fg="#f0f0f0", font=("Cascadia Mono", 9, "bold")).place(x=20, y=84)
        tk.Entry(window, textvariable=asset_name_var, bg="#1a1a1a", fg="#f0f0f0", insertbackground="#56f4ee").place(x=20, y=106, width=240, height=24)
        tk.Label(window, text="Folder", bg="#111111", fg="#f0f0f0", font=("Cascadia Mono", 9, "bold")).place(x=280, y=84)
        tk.Entry(window, textvariable=folder_var, bg="#1a1a1a", fg="#f0f0f0", insertbackground="#56f4ee").place(x=280, y=106, width=100, height=24)
        tk.Label(window, text="Source Type", bg="#111111", fg="#f0f0f0", font=("Cascadia Mono", 9, "bold")).place(x=20, y=144)
        ttk.Combobox(window, textvariable=mode_var, values=(["image", "prefab"] if allow_prefab else ["image"]), state="readonly").place(x=20, y=166, width=120, height=24)

        static_label = tk.Label(window, text="Static / Main File", bg="#111111", fg="#f0f0f0", font=("Cascadia Mono", 9, "bold"))
        static_label.place(x=20, y=206)
        static_entry = tk.Entry(window, textvariable=static_var, bg="#1a1a1a", fg="#f0f0f0", insertbackground="#56f4ee")
        static_entry.place(x=20, y=228, width=540, height=24)
        tk.Button(window, text="Browse", command=lambda: self._choose_visual_asset_file(window, mode_var.get(), static_var, preview_label)).place(x=574, y=226, width=80, height=28)

        animated_check = None
        anim_widgets = []
        if allow_animation:
            animated_check = tk.Checkbutton(window, text="Animated", variable=animated_var, bg="#111111", fg="#f0f0f0", activebackground="#111111", activeforeground="#56f4ee", selectcolor="#111111")
            animated_check.place(x=160, y=164)
            anim_label = tk.Label(window, text="Anim File", bg="#111111", fg="#f0f0f0", font=("Cascadia Mono", 9, "bold"))
            anim_entry = tk.Entry(window, textvariable=anim_var, bg="#1a1a1a", fg="#f0f0f0", insertbackground="#56f4ee")
            anim_button = tk.Button(window, text="Browse", command=lambda: self._choose_visual_asset_file(window, mode_var.get(), anim_var, None))
            anim_widgets = [anim_label, anim_entry, anim_button]
            anim_label.place(x=20, y=272)
            anim_entry.place(x=20, y=294, width=540, height=24)
            anim_button.place(x=574, y=292, width=80, height=28)

        def update_form(*_args):
            is_prefab = mode_var.get() == "prefab"
            if is_prefab:
                animated_var.set(False)
            if animated_check is not None:
                animated_check.configure(state=("disabled" if is_prefab else "normal"))
            show_anim = allow_animation and animated_var.get() and not is_prefab
            for widget in anim_widgets:
                widget.place_forget()
            if show_anim and len(anim_widgets) == 3:
                anim_widgets[0].place(x=20, y=272)
                anim_widgets[1].place(x=20, y=294, width=540, height=24)
                anim_widgets[2].place(x=574, y=292, width=80, height=28)
            if is_prefab:
                preview_label.configure(text="Prefab preview unavailable", image="")
                preview_label.image = None
            else:
                self._update_preview_label_from_path(preview_label, static_var.get().strip())

        if allow_animation:
            animated_var.trace_add("write", update_form)
        mode_var.trace_add("write", update_form)
        static_var.trace_add("write", update_form)

        def submit():
            key = self._slugify_project_id(tech_var.get().strip())
            if not key:
                self._show_lmr_warning("Invalid Name", "Enter a valid technical name.", window)
                return
            static_source = Path(static_var.get().strip()) if static_var.get().strip() else None
            if static_source is None or not static_source.exists():
                self._show_lmr_warning("Missing File", "Choose the main asset file.", window)
                return
            if mode_var.get() == "prefab":
                rel_path, _ = self._copy_lmr_asset_into_project(static_source, folder_var.get(), asset_name_var.get().strip() or None)
                entry_lines = [
                    f"    {key}:",
                    f"        static: ~@bundle[prefab]://{rel_path}",
                ] if allow_animation else [f"    {key}: ~@bundle[prefab]://{rel_path}"]
            else:
                static_rel, _ = self._copy_lmr_asset_into_project(static_source, folder_var.get(), asset_name_var.get().strip() or None)
                if allow_animation and animated_var.get():
                    anim_source = Path(anim_var.get().strip()) if anim_var.get().strip() else None
                    if anim_source is None or not anim_source.exists():
                        self._show_lmr_warning("Missing File", "Choose the animation asset file.", window)
                        return
                    anim_rel, _ = self._copy_lmr_asset_into_project(anim_source, folder_var.get(), f"{(asset_name_var.get().strip() or static_source.stem)}_anim")
                    entry_lines = [
                        f"    {key}:",
                        f"        static: {static_rel}",
                        f"        anim: {anim_rel}",
                    ]
                else:
                    entry_lines = [f"    {key}: {static_rel}"]
            self._upsert_lmr_named_entry(section_name, key, entry_lines)
            window.destroy()

        tk.Button(window, text="Add", command=submit).place(x=650, y=(474 if allow_animation else 404), width=80, height=28)
        tk.Button(window, text="Cancel", command=window.destroy).place(x=560, y=(474 if allow_animation else 404), width=80, height=28)
        update_form()
        window.grab_set()
        window.focus_force()

    def _choose_visual_asset_file(self, parent, mode: str, variable: tk.StringVar, preview_label):
        filetypes = [("Prefab", "*.prefab"), ("All files", "*.*")] if mode == "prefab" else [("Images", "*.png *.jpg *.jpeg *.webp"), ("All files", "*.*")]
        chosen = self._ask_open_file(parent, "Select asset file", filetypes)
        if not chosen:
            return
        variable.set(chosen)
        if preview_label is not None and mode != "prefab":
            self._update_preview_label_from_path(preview_label, chosen)

    def _detect_project_type(self) -> str | None:
        if self.project_dir is None:
            return None
        if (self.project_dir / "resources.yaml").exists() and (self.project_dir / "meta.yaml").exists():
            return "lmr"
        if any(path.suffix.lower() == ".rpy" for path in self.project_dir.iterdir() if path.is_file()):
            return "es"
        return None

    def _normalize_project_file_name(self, name: str, extension: str) -> str:
        cleaned = re.sub(r'[<>:"/\\\\|?*]+', "_", name.strip())
        if not cleaned:
            return ""
        if not cleaned.lower().endswith(extension.lower()):
            cleaned += extension
        return cleaned

    def _upsert_lmr_scenario_entry(self, scenario_name: str, scenario_rel_path: str):
        if self.project_dir is None:
            return
        resources_path = self.project_dir / "resources.yaml"
        if resources_path.exists():
            content = resources_path.read_text(encoding="utf-8")
        else:
            content = "---\n"

        lines = content.splitlines()
        scenario_header = None
        for index, line in enumerate(lines):
            if line.strip() == "scenarios:":
                scenario_header = index
                break

        scenario_rel_path = scenario_rel_path.replace("\\", "/")
        new_entry = f"    {scenario_name}: {scenario_rel_path}"

        if scenario_header is None:
            if lines and lines[-1].strip():
                lines.append("")
            lines.extend(["scenarios:", new_entry])
        else:
            block_end = len(lines)
            for index in range(scenario_header + 1, len(lines)):
                candidate = lines[index]
                if candidate and not candidate.startswith(" "):
                    block_end = index
                    break

            replaced = False
            for index in range(scenario_header + 1, block_end):
                if lines[index].strip().startswith(f"{scenario_name}:"):
                    lines[index] = new_entry
                    replaced = True
                    break
            if not replaced:
                insert_at = block_end
                while insert_at > scenario_header + 1 and lines[insert_at - 1] == "":
                    insert_at -= 1
                lines.insert(insert_at, new_entry)

        resources_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        updated_content = resources_path.read_text(encoding="utf-8")
        self.saved_file_snapshots[resources_path] = updated_content
        self.file_buffers[resources_path] = updated_content
        self.dirty_files.discard(resources_path)
        if self.current_file == resources_path and self.editor_text is not None:
            current_index = self.editor_text.index("insert")
            self._set_editor_content(updated_content)
            try:
                self.editor_text.mark_set("insert", current_index)
                self.editor_text.see(current_index)
            except tk.TclError:
                pass
            self._refresh_line_numbers(force=True)
            self._update_status(refresh_lines=False)
            self._request_render_file_tabs()

    def create_project_text_file(self, initial_state=None):
        if self.project_dir is None:
            messagebox.showwarning("No project", "Open a project first.", parent=self.root)
            return

        project_type = self._detect_project_type()
        if project_type not in {"lmr", "es"}:
            messagebox.showwarning("Unknown project", "Could not detect project type.", parent=self.root)
            return

        cfg = self.layout["create_file_window"]
        width = cfg["width"]
        height = cfg["height_lmr"] if project_type == "lmr" else cfg["height_es"]
        window = tk.Toplevel(self.root)
        window.transient(self.root)
        window.resizable(False, False)
        window.configure(bg=TRANSPARENT_COLOR)
        window.overrideredirect(True)
        try:
            window.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)
        except tk.TclError:
            pass
        try:
            window.wm_attributes("-topmost", True)
        except tk.TclError:
            pass
        window.geometry(
            f"{width}x{height}+{self.root.winfo_x() + max(0, (self.layout['window']['width'] - width) // 2)}+{self.root.winfo_y() + max(0, (self.layout['window']['height'] - height) // 2)}"
        )

        canvas = tk.Canvas(window, width=width, height=height, bg=TRANSPARENT_COLOR, highlightthickness=0, bd=0)
        canvas.pack()
        self._draw_window_frame(canvas, width, height)
        canvas.create_text(cfg["title_x"], cfg["title_y"], text="Create Project File", anchor="n", fill="#f0f0f0", font=("Cascadia Mono", 12, "bold"))

        initial_state = initial_state or {}
        kind_var = tk.StringVar(value=str(initial_state.get("kind", "scenario_txt" if project_type == "lmr" else "rpy_script")))
        name_var = tk.StringVar(value=str(initial_state.get("name", "")))
        folder_var = tk.StringVar(value=str(initial_state.get("folder", "")))
        technical_name_var = tk.StringVar(value=str(initial_state.get("technical_name", "")))

        panel_bg = "#101010"
        panel_border = "#1d1d1d"

        def add_label(x, y, text, color="#f0f0f0"):
            canvas.create_text(x, y, text=text, anchor="nw", fill=color, font=("Cascadia Mono", 9, "bold"))

        def add_entry(x, y, width_px, variable):
            entry = tk.Entry(
                window,
                textvariable=variable,
                font=("Cascadia Mono", 9),
                bg=panel_bg,
                fg="#f0f0f0",
                insertbackground="#56f4ee",
                bd=0,
                highlightthickness=1,
                highlightbackground=panel_border,
            )
            canvas.create_window(x, y, anchor="nw", window=entry, width=width_px, height=24)
            return entry

        toggle_rows = []

        def create_asset_toggle(x, y, label, variable, value, width_px=220):
            frame = tk.Frame(window, bg=panel_bg, bd=0, highlightthickness=0)
            frame.place(x=x, y=y, width=width_px, height=22)
            text_label = tk.Label(frame, text=label, bg=panel_bg, fg="#f0f0f0", font=("Cascadia Mono", 9, "bold"), anchor="w", justify="left")
            text_label.place(x=0, y=0, width=width_px - 28, height=22)
            icon_label = tk.Label(frame, bg=panel_bg, bd=0, highlightthickness=0)
            icon_label.place(x=width_px - 18, y=2, width=18, height=18)
            state = {"hovered": False}

            def refresh():
                checked = variable.get() == value
                icon_name = "checkbox_onmouse.png" if state["hovered"] else ("checkbox_on.png" if checked else "checkbox_off.png")
                text_label.configure(fg="#56f4ee" if state["hovered"] else "#f0f0f0")
                icon = self.assets.get(icon_name)
                icon_label.configure(image=icon)
                icon_label.image = icon

            def on_click(_event=None):
                variable.set(value)
                update_form_state()
                for row in toggle_rows:
                    row()

            def on_enter(_event=None):
                state["hovered"] = True
                refresh()

            def on_leave(_event=None):
                state["hovered"] = False
                refresh()

            for widget in (frame, text_label, icon_label):
                widget.bind("<Button-1>", on_click)
                widget.bind("<Enter>", on_enter)
                widget.bind("<Leave>", on_leave)

            toggle_rows.append(refresh)
            refresh()

        add_label(cfg["type_x"], cfg["type_y"], "Type")
        if project_type == "lmr":
            create_asset_toggle(cfg["type_x"], cfg["type_y"] + cfg["type_step_y"], "Scenario TXT", kind_var, "scenario_txt", width_px=cfg["type_item_width_lmr"])
            create_asset_toggle(cfg["type_x"], cfg["type_y"] + cfg["type_step_y"] * 2, "YAML (resources signature)", kind_var, "yaml_resources", width_px=cfg["type_item_width_lmr"])
            create_asset_toggle(cfg["type_x"], cfg["type_y"] + cfg["type_step_y"] * 3, "YAML (meta signature)", kind_var, "yaml_meta", width_px=cfg["type_item_width_lmr"])
        else:
            create_asset_toggle(cfg["type_x"], cfg["type_y"] + cfg["type_step_y"], "Ren'Py Script (.rpy)", kind_var, "rpy_script", width_px=cfg["type_item_width_es"])

        add_label(cfg["file_name_label_x"], cfg["file_name_label_y_lmr"] if project_type == "lmr" else cfg["file_name_label_y_es"], "File Name")
        name_entry = add_entry(cfg["file_name_entry_x"], cfg["file_name_entry_y_lmr"] if project_type == "lmr" else cfg["file_name_entry_y_es"], cfg["file_name_entry_width"], name_var)

        technical_name_label = None
        technical_name_entry = None
        folder_label = None
        folder_entry = None
        folder_note = None
        if project_type == "lmr":
            technical_name_label = canvas.create_text(cfg["technical_label_x"], cfg["technical_label_y"], text="Technical Name", anchor="nw", fill="#56f4ee", font=("Cascadia Mono", 9, "bold"))
            technical_name_entry = add_entry(cfg["technical_entry_x"], cfg["technical_entry_y"], cfg["technical_entry_width"], technical_name_var)
            folder_label = canvas.create_text(cfg["folder_label_x"], cfg["folder_label_y"], text="Scenario Folder (optional)", anchor="nw", fill="#56f4ee", font=("Cascadia Mono", 9, "bold"))
            folder_entry = add_entry(cfg["folder_entry_x"], cfg["folder_entry_y"], cfg["folder_entry_width"], folder_var)
            folder_note = canvas.create_text(
                cfg["folder_note_x"],
                cfg["folder_note_y"],
                text="Leave empty to create file in project root.",
                anchor="nw",
                fill="#9aa0a0",
                font=("Cascadia Mono", 8, "bold"),
            )

        create_file_layout_mtime = self._get_layout_mtime()

        def capture_create_file_state():
            return {
                "kind": kind_var.get(),
                "name": name_var.get(),
                "folder": folder_var.get(),
                "technical_name": technical_name_var.get(),
            }

        def watch_create_file_layout():
            if not window.winfo_exists():
                return
            current_mtime = self._get_layout_mtime()
            if current_mtime != create_file_layout_mtime:
                state = capture_create_file_state()
                try:
                    window.grab_release()
                except tk.TclError:
                    pass
                window.destroy()
                self.layout_mtime = current_mtime
                self.layout = self._sanitize_layout(load_json(LAYOUT_PATH, DEFAULT_LAYOUT))
                self.root.after(20, lambda s=state: self.create_project_text_file(s))
                return
            window.after(350, watch_create_file_layout)

        def update_form_state(*_args):
            is_scenario = project_type == "lmr" and kind_var.get() == "scenario_txt"
            if folder_entry is not None:
                folder_entry.configure(state=("normal" if is_scenario else "disabled"))
            if technical_name_entry is not None:
                technical_name_entry.configure(state=("normal" if is_scenario else "disabled"))
            if folder_note is not None:
                canvas.itemconfigure(folder_note, state=("normal" if is_scenario else "hidden"))
            if technical_name_label is not None:
                canvas.itemconfigure(technical_name_label, state=("normal" if is_scenario else "hidden"))
            if folder_label is not None:
                canvas.itemconfigure(folder_label, state=("normal" if is_scenario else "hidden"))
            for refresh in toggle_rows:
                refresh()

        def close_dialog():
            try:
                window.grab_release()
            except tk.TclError:
                pass
            window.destroy()
            self._focus_editor_widget()

        def create_action():
            raw_name = name_var.get().strip()
            if not raw_name:
                messagebox.showwarning("Missing Name", "Enter a file name.", parent=window)
                return

            if project_type == "lmr":
                file_kind = kind_var.get()
                extension = ".txt" if file_kind == "scenario_txt" else ".yaml"
            else:
                file_kind = "rpy_script"
                extension = ".rpy"

            file_name = self._normalize_project_file_name(raw_name, extension)
            if not file_name:
                messagebox.showwarning("Invalid Name", "Enter a valid file name.", parent=window)
                return

            target_dir = self.project_dir
            scenario_rel_path = file_name
            scenario_key = Path(file_name).stem
            resources_path = self.project_dir / "resources.yaml"
            showing_resources = self.current_file == resources_path

            if project_type == "lmr" and file_kind == "scenario_txt":
                raw_technical_name = technical_name_var.get().strip()
                if raw_technical_name:
                    scenario_key = self._slugify_project_id(raw_technical_name)
                if not scenario_key:
                    messagebox.showwarning("Invalid Technical Name", "Enter a valid technical name.", parent=window)
                    return
                folder_name = folder_var.get().strip()
                if folder_name:
                    if "/" in folder_name or "\\" in folder_name:
                        messagebox.showwarning("Invalid Folder", "Only one folder name is allowed.", parent=window)
                        return
                    folder_name = re.sub(r'[<>:"/\\\\|?*]+', "_", folder_name)
                    if not folder_name:
                        messagebox.showwarning("Invalid Folder", "Enter a valid folder name.", parent=window)
                        return
                    target_dir = self.project_dir / folder_name
                    scenario_rel_path = f"{folder_name}/{file_name}"

            target_dir.mkdir(parents=True, exist_ok=True)
            target_path = target_dir / file_name
            if target_path.exists():
                messagebox.showwarning("File Exists", f"File already exists:\n{target_path}", parent=window)
                return

            if project_type == "lmr":
                if file_kind == "yaml_resources":
                    content = self._build_lmr_resources_yaml([])
                elif file_kind == "yaml_meta":
                    content = self._build_lmr_meta_yaml("", "", "0.1.0", None)
                else:
                    content = ""
            else:
                content = ""

            target_path.write_text(content, encoding="utf-8")

            if project_type == "lmr" and file_kind == "scenario_txt":
                self._upsert_lmr_scenario_entry(scenario_key, scenario_rel_path)

            self._reload_project_files()
            close_dialog()
            def finalize_open():
                if showing_resources and resources_path.exists():
                    self.open_file(resources_path)
                else:
                    self.open_file(target_path)
                self._focus_editor_widget()
            self.root.after(20, finalize_open)

        update_form_state()
        self._create_composite_button(window, canvas, cfg["return_x"], cfg["actions_y_lmr"] if project_type == "lmr" else cfg["actions_y_es"], "Return", 80, 24, close_dialog)
        self._create_composite_button(window, canvas, cfg["create_x"], cfg["actions_y_lmr"] if project_type == "lmr" else cfg["actions_y_es"], "Create", 80, 24, create_action)
        name_entry.focus_set()
        window.bind("<Escape>", lambda _e: close_dialog())
        window.after(350, watch_create_file_layout)
        window.grab_set()
        window.deiconify()
        window.lift()
        window.focus_force()
        window.wait_window()

    def create_mod_project(self, initial_state=None):
        result = {"created": False}
        cfg = self.layout["create_project_window"]
        general_cfg = cfg["general"]
        lmr_cfg = cfg["lmr"]
        es_cfg = cfg["es"]
        width = cfg["width"]
        height = cfg["height"]
        window = tk.Toplevel(self.root)
        window.transient(self.root)
        window.resizable(False, False)
        window.configure(bg=TRANSPARENT_COLOR)
        window.overrideredirect(True)
        try:
            window.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)
        except tk.TclError:
            pass
        try:
            window.wm_attributes("-topmost", True)
        except tk.TclError:
            pass
        window.geometry(
            f"{width}x{height}+{self.root.winfo_x() + max(0, (self.layout['window']['width'] - width) // 2)}+{self.root.winfo_y() + max(0, (self.layout['window']['height'] - height) // 2)}"
        )
        canvas = tk.Canvas(window, width=width, height=height, bg=TRANSPARENT_COLOR, highlightthickness=0, bd=0)
        canvas.pack()
        self._draw_window_frame(canvas, width, height)
        canvas.create_text(cfg["title_x"], cfg["title_y"], text="Create Project", anchor="n", fill="#f0f0f0", font=("Cascadia Mono", 12, "bold"))

        def run_project_dialog(callback):
            try:
                window.wm_attributes("-topmost", False)
            except tk.TclError:
                pass
            try:
                return callback()
            finally:
                try:
                    window.wm_attributes("-topmost", True)
                except tk.TclError:
                    pass
                try:
                    window.lift()
                    window.focus_force()
                except tk.TclError:
                    pass

        def show_project_warning(title, message):
            return run_project_dialog(lambda: messagebox.showwarning(title, message, parent=window))

        panel_bg = "#101010"
        panel_border = "#1d1d1d"
        initial_state = initial_state or {}
        game_var = tk.StringVar(value=str(initial_state.get("game", "lmr")))
        panel_var = tk.StringVar(value=str(initial_state.get("panel", "general")))
        game_path_var = tk.StringVar(value=str(initial_state.get("game_path", "")))
        project_id_var = tk.StringVar(value=str(initial_state.get("project_id", "")))
        lmr_title_var = tk.StringVar(value=str(initial_state.get("lmr_title", "")))
        lmr_version_var = tk.StringVar(value=str(initial_state.get("lmr_version", "0.1.0")))
        es_display_name_var = tk.StringVar(value=str(initial_state.get("es_display_name", "")))
        cover_path_var = tk.StringVar(value=str(initial_state.get("cover_path", "")))
        target_path_var = tk.StringVar()

        content_frame = tk.Frame(window, bg=panel_bg, bd=0, highlightthickness=1, highlightbackground=panel_border)
        canvas.create_window(cfg["content_x"], cfg["content_y"], anchor="nw", window=content_frame, width=cfg["content_width"], height=cfg["content_height"])
        general_frame = tk.Frame(content_frame, bg=panel_bg, bd=0, highlightthickness=0)
        lmr_frame = tk.Frame(content_frame, bg=panel_bg, bd=0, highlightthickness=0)
        es_frame = tk.Frame(content_frame, bg=panel_bg, bd=0, highlightthickness=0)
        for frame in (general_frame, lmr_frame, es_frame):
            frame.place(x=0, y=0, relwidth=1.0, relheight=1.0)

        lmr_description_widget = tk.Text(
            lmr_frame,
            width=30,
            height=4,
            font=("Cascadia Mono", 9),
            bg=panel_bg,
            fg="#f0f0f0",
            insertbackground="#56f4ee",
            bd=0,
            highlightthickness=1,
            highlightbackground=panel_border,
            wrap="word",
        )
        if initial_state.get("lmr_description"):
            lmr_description_widget.insert("1.0", str(initial_state.get("lmr_description", "")))

        section_state = initial_state.get("sections", {})
        section_vars = {
            "backdrop_bg": tk.BooleanVar(value=bool(section_state.get("backdrop_bg", False))),
            "backdrop_text": tk.BooleanVar(value=bool(section_state.get("backdrop_text", False))),
            "bg": tk.BooleanVar(value=bool(section_state.get("bg", False))),
            "cg": tk.BooleanVar(value=bool(section_state.get("cg", False))),
            "catalogs": tk.BooleanVar(value=bool(section_state.get("catalogs", False))),
            "characters": tk.BooleanVar(value=bool(section_state.get("characters", False))),
            "chibis": tk.BooleanVar(value=bool(section_state.get("chibis", False))),
            "collections": tk.BooleanVar(value=bool(section_state.get("collections", False))),
            "colors": tk.BooleanVar(value=bool(section_state.get("colors", False))),
            "entryPoint": tk.BooleanVar(value=bool(section_state.get("entryPoint", True))),
            "help": tk.BooleanVar(value=bool(section_state.get("help", False))),
            "live2d_characters": tk.BooleanVar(value=bool(section_state.get("live2d_characters", False))),
            "menu": tk.BooleanVar(value=bool(section_state.get("menu", False))),
            "particles": tk.BooleanVar(value=bool(section_state.get("particles", False))),
            "positions": tk.BooleanVar(value=bool(section_state.get("positions", False))),
            "scenarios": tk.BooleanVar(value=bool(section_state.get("scenarios", True))),
            "sizes": tk.BooleanVar(value=bool(section_state.get("sizes", False))),
            "sound": tk.BooleanVar(value=bool(section_state.get("sound", True))),
            "spritecolor": tk.BooleanVar(value=bool(section_state.get("spritecolor", False))),
            "variables": tk.BooleanVar(value=bool(section_state.get("variables", True))),
            "transitions": tk.BooleanVar(value=bool(section_state.get("transitions", False))),
        }

        def add_canvas_label(x, y, text, color="#f0f0f0", anchor="nw"):
            canvas.create_text(x, y, text=text, anchor=anchor, fill=color, font=("Cascadia Mono", 9, "bold"))

        def add_panel_label(parent, x, y, text, color="#f0f0f0"):
            label = tk.Label(parent, text=text, bg=panel_bg, fg=color, font=("Cascadia Mono", 9, "bold"), anchor="w", justify="left")
            label.place(x=x, y=y)
            return label

        def add_panel_text(parent, x, y, text, color="#9aa0a0", width_px=560):
            label = tk.Label(parent, text=text, bg=panel_bg, fg=color, font=("Cascadia Mono", 8, "bold"), anchor="nw", justify="left", wraplength=width_px)
            label.place(x=x, y=y)
            return label

        def add_panel_entry(parent, x, y, width_px, variable):
            entry = tk.Entry(
                parent,
                textvariable=variable,
                font=("Cascadia Mono", 9),
                bg=panel_bg,
                fg="#f0f0f0",
                insertbackground="#56f4ee",
                bd=0,
                highlightthickness=1,
                highlightbackground=panel_border,
            )
            entry.place(x=x, y=y, width=width_px, height=24)
            return entry

        toggle_rows = []

        def create_asset_toggle(parent, x, y, label, variable, *, value=True, kind="checkbox", command=None, disabled=False, width_px=180, icon_side="left"):
            frame = tk.Frame(parent, bg=panel_bg, bd=0, highlightthickness=0)
            frame.place(x=x, y=y, width=width_px, height=22)
            icon_label = tk.Label(frame, bg=panel_bg, bd=0, highlightthickness=0)
            text_label = tk.Label(frame, text=label, bg=panel_bg, fg="#f0f0f0", font=("Cascadia Mono", 9, "bold"), anchor="w", justify="left")
            if icon_side == "right":
                text_label.place(x=0, y=0, width=width_px - 28, height=22)
                icon_label.place(x=width_px - 18, y=2, width=18, height=18)
            else:
                icon_label.place(x=0, y=2, width=18, height=18)
                text_label.place(x=28, y=0, width=width_px - 28, height=22)
            state = {"hovered": False, "disabled": disabled}

            def is_checked():
                return variable.get() == value if kind == "radio" else bool(variable.get())

            def refresh():
                checked = is_checked()
                if state["disabled"]:
                    icon_name = "checkbox_on.png" if checked else "checkbox_off.png"
                    text_color = "#6e6e6e"
                elif state["hovered"]:
                    icon_name = "checkbox_onmouse.png"
                    text_color = "#56f4ee"
                else:
                    icon_name = "checkbox_on.png" if checked else "checkbox_off.png"
                    text_color = "#f0f0f0"
                icon = self.assets.get(icon_name)
                icon_label.configure(image=icon)
                icon_label.image = icon
                text_label.configure(fg=text_color)

            def set_disabled(disabled_value: bool):
                state["disabled"] = bool(disabled_value)
                state["hovered"] = False
                refresh()

            def on_click(_event=None):
                if state["disabled"]:
                    return
                if kind == "radio":
                    variable.set(value)
                else:
                    variable.set(not bool(variable.get()))
                if command:
                    command()
                for row in toggle_rows:
                    row["refresh"]()

            def on_enter(_event=None):
                if state["disabled"]:
                    return
                state["hovered"] = True
                refresh()

            def on_leave(_event=None):
                state["hovered"] = False
                refresh()

            for widget in (frame, icon_label, text_label):
                widget.bind("<Button-1>", on_click)
                widget.bind("<Enter>", on_enter)
                widget.bind("<Leave>", on_leave)

            row = {
                "frame": frame,
                "refresh": refresh,
                "set_disabled": set_disabled,
            }
            toggle_rows.append(row)
            refresh()
            return row

        add_canvas_label(cfg["game_label_x"], cfg["game_label_y"], "Game")
        game_rows = []
        for offset, game in enumerate(SUPPORTED_MOD_GAMES):
            label = game["name"] + (" (Locked)" if game["id"] == "es2" else "")
            row = create_asset_toggle(
                window,
                cfg["game_x"],
                cfg["game_y"] + offset * cfg["game_step_y"],
                label,
                game_var,
                value=game["id"],
                kind="radio",
                disabled=(game["id"] == "es2"),
                width_px=cfg["game_item_width"],
            )
            game_rows.append(row)

        add_canvas_label(cfg["menu_label_x"], cfg["menu_label_y"], "Project Settings")
        panel_rows = {}

        def show_project_panel(name: str):
            panel_var.set(name)
            {"general": general_frame, "lmr": lmr_frame, "es": es_frame}[name].tkraise()
            for row in toggle_rows:
                row["refresh"]()

        panel_rows["general"] = create_asset_toggle(window, cfg["menu_x"], cfg["menu_y"], "Common", panel_var, value="general", kind="radio", command=lambda: show_project_panel("general"), width_px=cfg["menu_item_width"], icon_side="right")
        panel_rows["lmr"] = create_asset_toggle(window, cfg["menu_x"], cfg["menu_y"] + cfg["menu_step_y"], "LMR", panel_var, value="lmr", kind="radio", command=lambda: show_project_panel("lmr"), width_px=cfg["menu_item_width"], icon_side="right")
        panel_rows["es"] = create_asset_toggle(window, cfg["menu_x"], cfg["menu_y"] + cfg["menu_step_y"] * 2, "Everlasting Summer", panel_var, value="es", kind="radio", command=lambda: show_project_panel("es"), width_px=cfg["menu_item_width"], icon_side="right")

        add_panel_label(general_frame, general_cfg["game_folder_label_x"], general_cfg["game_folder_label_y"], "Game Folder")
        game_folder_entry = add_panel_entry(general_frame, general_cfg["game_folder_entry_x"], general_cfg["game_folder_entry_y"], general_cfg["game_folder_entry_width"], game_path_var)

        def browse_game_folder():
            folder = run_project_dialog(lambda: filedialog.askdirectory(title="Select game folder", parent=window))
            if folder:
                game_path_var.set(folder)
                window.lift()
                window.focus_force()

        browse_game_widget, _browse_game_item = self._create_composite_button(
            general_frame,
            None,
            general_cfg["browse_x"],
            general_cfg["browse_y"],
            "Browse",
            general_cfg["browse_width"],
            24,
            browse_game_folder,
        )

        add_panel_label(general_frame, general_cfg["project_id_label_x"], general_cfg["project_id_label_y"], "Project ID")
        project_id_entry = add_panel_entry(general_frame, general_cfg["project_id_entry_x"], general_cfg["project_id_entry_y"], general_cfg["project_id_entry_width"], project_id_var)
        add_panel_text(general_frame, general_cfg["project_id_hint_x"], general_cfg["project_id_hint_y"], "Allowed: latin, digits and _", "#9aa0a0", 240)
        add_panel_label(general_frame, general_cfg["target_label_x"], general_cfg["target_label_y"], "Target Folder")
        target_label = tk.Label(general_frame, textvariable=target_path_var, bg=panel_bg, fg="#56f4ee", font=("Cascadia Mono", 8, "bold"), anchor="nw", justify="left", wraplength=560)
        target_label.place(x=general_cfg["target_value_x"], y=general_cfg["target_value_y"], width=general_cfg["target_value_width"], height=general_cfg["target_value_height"])
        add_panel_text(general_frame, general_cfg["note_x"], general_cfg["note_y"], "Choose the game first, then fill the game folder and project id.", "#d7d9d7", 560)

        add_panel_label(lmr_frame, lmr_cfg["title_label_x"], lmr_cfg["title_label_y"], "LMR Title")
        lmr_title_entry = add_panel_entry(lmr_frame, lmr_cfg["title_entry_x"], lmr_cfg["title_entry_y"], lmr_cfg["title_entry_width"], lmr_title_var)
        add_panel_label(lmr_frame, lmr_cfg["version_label_x"], lmr_cfg["version_label_y"], "Version")
        lmr_version_entry = add_panel_entry(lmr_frame, lmr_cfg["version_entry_x"], lmr_cfg["version_entry_y"], lmr_cfg["version_entry_width"], lmr_version_var)
        add_panel_label(lmr_frame, lmr_cfg["description_label_x"], lmr_cfg["description_label_y"], "LMR Description")
        lmr_description_widget.place(x=lmr_cfg["description_x"], y=lmr_cfg["description_y"], width=lmr_cfg["description_width"], height=lmr_cfg["description_height"])

        add_panel_label(lmr_frame, lmr_cfg["cover_label_x"], lmr_cfg["cover_label_y"], "Cover")
        cover_entry = add_panel_entry(lmr_frame, lmr_cfg["cover_entry_x"], lmr_cfg["cover_entry_y"], lmr_cfg["cover_entry_width"], cover_path_var)
        add_panel_label(lmr_frame, lmr_cfg["cover_warning_label_x"], lmr_cfg["cover_warning_label_y"], "Cover warning:", "#56f4ee")
        add_panel_text(lmr_frame, lmr_cfg["cover_warning_1_x"], lmr_cfg["cover_warning_1_y"], "optional, not required", "#d7d9d7", 150)
        add_panel_text(lmr_frame, lmr_cfg["cover_warning_2_x"], lmr_cfg["cover_warning_2_y"], "2 MB / 445x200 recommended", "#d7d9d7", 170)

        def browse_cover_file():
            path = run_project_dialog(
                lambda: filedialog.askopenfilename(
                    title="Select cover image",
                    filetypes=[("Image files", "*.png;*.jpg;*.jpeg"), ("PNG", "*.png"), ("JPEG", "*.jpg;*.jpeg")],
                    parent=window,
                )
            )
            if not path:
                return
            cover_path_var.set(path)
            cover_file = Path(path)
            warnings = []
            try:
                if cover_file.stat().st_size > 2 * 1024 * 1024:
                    warnings.append("Cover is larger than 2 MB.")
            except OSError:
                pass
            if Image is not None:
                try:
                    with Image.open(cover_file) as cover_image:
                        if cover_image.size != (445, 200):
                            warnings.append(f"Recommended resolution is 445x200, current: {cover_image.size[0]}x{cover_image.size[1]}.")
                except OSError:
                    pass
            if warnings:
                show_project_warning("Cover Warning", "\n".join(warnings))
            window.lift()
            window.focus_force()

        browse_cover_widget, _browse_cover_item = self._create_composite_button(
            lmr_frame,
            None,
            lmr_cfg["cover_button_x"],
            lmr_cfg["cover_button_y"],
            "Choose",
            lmr_cfg["cover_button_width"],
            24,
            browse_cover_file,
        )

        add_panel_label(lmr_frame, lmr_cfg["resources_label_x"], lmr_cfg["resources_label_y"], "resources.yaml sections")
        section_labels = [
            ("backdrop_bg", "backdrop_bg"),
            ("backdrop_text", "backdrop_text"),
            ("bg", "bg"),
            ("cg", "cg"),
            ("catalogs", "catalogs"),
            ("characters", "characters"),
            ("chibis", "chibis"),
            ("collections", "collections"),
            ("colors", "colors"),
            ("entryPoint", "entryPoint"),
            ("help", "help"),
            ("live2d_characters", "live2d_characters"),
            ("menu", "menu"),
            ("particles", "particles"),
            ("positions", "positions"),
            ("scenarios", "scenarios"),
            ("sizes", "sizes"),
            ("sound", "sound"),
            ("spritecolor", "spritecolor"),
            ("transitions", "transitions"),
            ("variables", "variables"),
        ]
        section_rows = []
        for index, (key, label) in enumerate(section_labels):
            row_x = lmr_cfg["resources_x"] + (index % 3) * lmr_cfg["resources_column_width"]
            row_y = lmr_cfg["resources_y"] + (index // 3) * lmr_cfg["resources_row_height"]
            section_rows.append(create_asset_toggle(lmr_frame, row_x, row_y, label, section_vars[key], width_px=182))

        add_panel_label(es_frame, es_cfg["display_label_x"], es_cfg["display_label_y"], "ES Display Name")
        es_display_entry = add_panel_entry(es_frame, es_cfg["display_entry_x"], es_cfg["display_entry_y"], es_cfg["display_entry_width"], es_display_name_var)
        add_panel_text(es_frame, es_cfg["note_1_x"], es_cfg["note_1_y"], "This name will be shown in the in-game mod list.", "#9aa0a0", 420)
        add_panel_text(es_frame, es_cfg["note_2_x"], es_cfg["note_2_y"], "The generated .rpy file will be saved in UTF-8 inside game/mods/<project_id>.", "#d7d9d7", 520)

        def update_target_path():
            project_id = project_id_var.get().strip() or "<project_id>"
            if game_var.get() == "lmr":
                target_path_var.set(f"Love, Money, Rock'n'Roll_Data/mods/{project_id}")
            else:
                target_path_var.set(f"game/mods/{project_id}")

        def update_form_state(*_args):
            is_lmr = game_var.get() == "lmr"
            lmr_state = "normal" if is_lmr else "disabled"
            es_state = "normal" if game_var.get() == "es" else "disabled"
            for widget in (lmr_description_widget, lmr_title_entry, lmr_version_entry, cover_entry):
                widget.configure(state=lmr_state)
            es_display_entry.configure(state=es_state)
            panel_rows["lmr"]["set_disabled"](not is_lmr)
            panel_rows["es"]["set_disabled"](game_var.get() != "es")
            for row in section_rows:
                row["set_disabled"](not is_lmr)
            if panel_var.get() == "lmr" and not is_lmr:
                show_project_panel("general")
            elif panel_var.get() == "es" and game_var.get() != "es":
                show_project_panel("general")
            update_target_path()

        game_var.trace_add("write", update_form_state)
        project_id_var.trace_add("write", lambda *_args: update_target_path())

        def sync_project_id(*_args):
            if project_id_var.get().strip():
                return
            lmr_source = lmr_title_var.get().strip() or es_display_name_var.get().strip()
            if lmr_source:
                project_id_var.set(self._slugify_project_id(lmr_source))

        lmr_title_var.trace_add("write", sync_project_id)
        es_display_name_var.trace_add("write", sync_project_id)

        def capture_project_state():
            return {
                "game": game_var.get(),
                "panel": panel_var.get(),
                "game_path": game_path_var.get(),
                "project_id": project_id_var.get(),
                "lmr_title": lmr_title_var.get(),
                "lmr_version": lmr_version_var.get(),
                "es_display_name": es_display_name_var.get(),
                "cover_path": cover_path_var.get(),
                "lmr_description": lmr_description_widget.get("1.0", "end-1c"),
                "sections": {key: bool(variable.get()) for key, variable in section_vars.items()},
            }

        create_project_layout_mtime = self._get_layout_mtime()
        recreate_state = {"data": None}

        def watch_create_project_layout():
            if not window.winfo_exists():
                return
            current_mtime = self._get_layout_mtime()
            if current_mtime != create_project_layout_mtime:
                recreate_state["data"] = capture_project_state()
                try:
                    window.grab_release()
                except tk.TclError:
                    pass
                window.destroy()
                self.layout_mtime = current_mtime
                self.layout = self._sanitize_layout(load_json(LAYOUT_PATH, DEFAULT_LAYOUT))
                self.root.after(20, lambda state=recreate_state["data"]: self.create_mod_project(state))
                return
            window.after(350, watch_create_project_layout)

        def close_dialog():
            try:
                window.grab_release()
            except tk.TclError:
                pass
            window.destroy()
            self._focus_editor_widget()

        def create_project_action():
            game_id = game_var.get()
            game_root = Path(game_path_var.get().strip())
            project_id = project_id_var.get().strip()

            if game_id == "es2":
                show_project_warning("Unavailable", "Everlasting Summer: 2 isn't released.")
                return
            if not game_root.exists():
                show_project_warning("Invalid Folder", "Select a valid game folder.")
                return
            if not self._is_valid_project_id(project_id):
                show_project_warning("Invalid Project ID", "Project ID may contain only latin letters, digits and underscores.")
                return

            if game_id == "lmr":
                exe_name = "Love, Money, Rock'n'Roll.exe"
                mods_root = game_root / "Love, Money, Rock'n'Roll_Data" / "mods"
            else:
                exe_name = "Everlasting Summer.exe"
                mods_root = game_root / "game" / "mods"

            if not (game_root / exe_name).exists():
                show_project_warning("Game Not Found", f"Required file was not found:\n{game_root / exe_name}")
                return

            project_dir = mods_root / project_id
            if project_dir.exists() and any(project_dir.iterdir()):
                show_project_warning("Project Exists", f"Folder already exists and is not empty:\n{project_dir}")
                return
            mods_root.mkdir(parents=True, exist_ok=True)
            project_dir.mkdir(parents=True, exist_ok=True)

            if game_id == "lmr":
                title = lmr_title_var.get().strip()
                description = lmr_description_widget.get("1.0", "end-1c").strip()
                version = lmr_version_var.get().strip() or "0.1.0"
                if not title:
                    show_project_warning("Missing Title", "Enter title for meta.yaml.")
                    return
                selected_sections = [key for key, _label in section_labels if section_vars[key].get()]
                resources_yaml = self._build_lmr_resources_yaml(selected_sections)
                cover_rel_path = None
                cover_source = cover_path_var.get().strip()
                if cover_source:
                    cover_src_path = Path(cover_source)
                    if cover_src_path.exists():
                        images_dir = project_dir / "images"
                        images_dir.mkdir(parents=True, exist_ok=True)
                        cover_ext = cover_src_path.suffix.lower() if cover_src_path.suffix.lower() in {".png", ".jpg", ".jpeg"} else ".png"
                        cover_dest = images_dir / f"cover{cover_ext}"
                        shutil.copy2(cover_src_path, cover_dest)
                        cover_rel_path = f"images/{cover_dest.name}"
                meta_yaml = self._build_lmr_meta_yaml(title, description, version, cover_rel_path)
                (project_dir / "resources.yaml").write_text(resources_yaml, encoding="utf-8")
                (project_dir / "meta.yaml").write_text(meta_yaml, encoding="utf-8")
            else:
                display_name = es_display_name_var.get().strip()
                if not display_name:
                    show_project_warning("Missing Name", "Enter the translated display name for the mod.")
                    return
                script_content = (
                    "init:\n\n"
                    f"\t$ mods[\"{project_id}\"] = u\"{display_name}\"\n\n"
                    "label start:\n"
                )
                (project_dir / f"{project_id}.rpy").write_text(script_content, encoding="utf-8")

            result["created"] = True
            close_dialog()
            self._set_project_dir(project_dir)

        update_form_state()
        show_project_panel("general")

        self._create_composite_button(window, canvas, cfg["return_x"], cfg["actions_y"], "Return", 80, 24, close_dialog)
        self._create_composite_button(window, canvas, cfg["create_x"], cfg["actions_y"], "Create", 80, 24, create_project_action)
        window.bind("<Escape>", lambda _e: close_dialog())
        window.after(350, watch_create_project_layout)
        window.grab_set()
        window.deiconify()
        window.lift()
        window.focus_force()
        window.wait_window()

    def open_project(self):
        folder = filedialog.askdirectory(title="Select mod project folder")
        if not folder:
            return
        self._set_project_dir(Path(folder))

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
            self.file_buffers[self.current_file] = self._get_editor_content()
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = path.read_text(encoding="utf-8", errors="replace")
        if path not in self.open_files:
            self.open_files.append(path)
        self.current_file = path
        self.saved_file_snapshots[path] = content
        content = self.file_buffers.get(path, content)
        self.file_buffers[path] = content
        self.dirty_files.discard(path)
        self._set_editor_content(content)
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
        if self._is_file_dirty(path):
            should_close = self._show_unsaved_warning(
                "Unsaved File",
                f"{path.name} has unsaved changes.\nExit this file without saving?",
            )
            if not should_close:
                return
        was_current = path == self.current_file
        current_index = self.open_files.index(path)
        self.open_files.remove(path)
        self.file_buffers.pop(path, None)
        self.saved_file_snapshots.pop(path, None)
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
        content = self._get_editor_content()
        if self.current_file is None:
            if not content.strip():
                self._focus_editor_widget()
                return
            destination = filedialog.asksaveasfilename(
                title="Save file as",
                initialdir=str(self.project_dir) if self.project_dir else str(BASE_DIR),
                defaultextension=".rpy",
                filetypes=[
                    ("Ren'Py script", "*.rpy"),
                    ("YAML file", "*.yaml"),
                    ("Text file", "*.txt"),
                ],
            )
            if not destination:
                self._focus_editor_widget()
                return
            path = Path(destination)
            path.parent.mkdir(parents=True, exist_ok=True)
            self.current_file = path
            if path not in self.open_files:
                self.open_files.append(path)
        self.file_buffers[self.current_file] = content
        self.current_file.write_text(content, encoding="utf-8")
        self.saved_file_snapshots[self.current_file] = content
        self.dirty_files.discard(self.current_file)
        self._update_status()
        self._request_render_file_tabs()
        self._focus_editor_widget()

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
        if self.editor_text is None or self.line_numbers is None:
            return
        try:
            canvas_height = max(1, self.line_numbers.winfo_height())
            canvas_width = max(1, self.line_numbers.winfo_width())
            top_index = self.editor_text.index("@0,0")
            top_dline = self.editor_text.dlineinfo(top_index)
        except tk.TclError:
            return
        real_line_count = self._get_editor_line_count()
        top_y = 0 if top_dline is None else int(top_dline[1])
        viewport_signature = (top_index, top_y, canvas_height, canvas_width, real_line_count)
        if not force and viewport_signature == getattr(self, "last_line_top_index", None):
            return
        self.last_line_top_index = viewport_signature
        self.line_numbers.delete("all")
        index = top_index
        while True:
            dline = self.editor_text.dlineinfo(index)
            if dline is None:
                break
            y = int(dline[1])
            line_height = int(dline[3])
            if y > canvas_height:
                break
            line_number = index.split(".", 1)[0]
            if int(line_number) > real_line_count:
                break
            self.line_numbers.create_text(
                canvas_width - 4,
                y,
                anchor="ne",
                text=line_number,
                fill="#6e6e6e",
                font=("Cascadia Mono", 10),
            )
            next_index = self.editor_text.index(f"{index}+1line linestart")
            if next_index == index:
                break
            if y + line_height >= canvas_height:
                break
            index = next_index

    def _schedule_line_numbers_refresh(self):
        if self.line_numbers_refresh_job is not None:
            try:
                self.root.after_cancel(self.line_numbers_refresh_job)
            except tk.TclError:
                pass
        self.line_numbers_refresh_job = self.root.after(120, self._line_numbers_refresh_tick)

    def _line_numbers_refresh_tick(self):
        self.line_numbers_refresh_job = None
        try:
            self._refresh_line_numbers(force=False)
        except tk.TclError:
            return
        self._schedule_line_numbers_refresh()

    def _update_status(self, refresh_lines=True):
        game_name = self._get_project_game_name()
        current_name = self.current_file.name if self.current_file else "No file open"
        line, column = self.editor_text.index("insert").split(".") if self.editor_text is not None else ("1", "0")
        self.canvas.itemconfigure(self.mode_id, text=f"Mode: {game_name}")
        self.canvas.itemconfigure(self.cursor_id, text=f"{current_name}   String: {line}   Column: {column}")
        if refresh_lines:
            self._refresh_line_numbers()

    def _update_presence(self):
        project_name = self._get_presence_project_name()
        file_name = self._get_project_game_name()
        self.discord.update(project_name, file_name)

    def _presence_loop(self):
        self.discord.ensure()
        self.root.after(15000, self._presence_loop)

    def on_close(self):
        unsaved_files = [path for path in self.open_files if self._is_file_dirty(path)]
        if unsaved_files:
            if len(unsaved_files) == 1:
                message = f"{unsaved_files[0].name} has unsaved changes.\nExit the editor without saving?"
            else:
                message = f"There are {len(unsaved_files)} unsaved files.\nExit the editor without saving?"
            should_exit = self._show_unsaved_warning("Unsaved Changes", message)
            if not should_exit:
                return
        self.close_settings_window()
        self.discord.clear()
        if self.line_numbers_refresh_job is not None:
            try:
                self.root.after_cancel(self.line_numbers_refresh_job)
            except tk.TclError:
                pass
        self.root.destroy()


def main():
    root = tk.Tk()
    app = EditorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
