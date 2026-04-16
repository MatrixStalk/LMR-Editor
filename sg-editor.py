import json
import os
import shutil
import time
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinter.scrolledtext import ScrolledText

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

try:
    from pypresence import Presence
except ImportError:
    Presence = None


TEXT_EXTENSIONS = {
    ".json",
    ".md",
    ".py",
    ".rpy",
    ".rpym",
    ".toml",
    ".txt",
    ".xml",
    ".yml",
    ".yaml",
}

SNIPPETS = {
    "Character declaration": 'define hero = Character("Hero")\n',
    "Scene + show": 'scene bg street_day\nshow hero neutral at center\nwith dissolve\n',
    "Dialogue block": 'hero "First line."\nhero "Second line."\n',
    "Menu choice": 'menu:\n    "Ask about the city":\n        jump ask_city\n    "Stay silent":\n        jump stay_silent\n',
    "Label": 'label new_scene:\n    "Scene starts here."\n    return\n',
    "Conditional": 'if flag_name:\n    hero "Condition is true."\nelse:\n    hero "Condition is false."\n',
    "Call screen": 'call screen phone_ui\n',
    "Image declaration": 'image hero neutral = "images/hero/neutral.png"\n',
}

BASE_DIR = Path(__file__).resolve().parent
DISCORD_RPC_PATH = BASE_DIR / "discordrpc"
ASSETS_DIR = BASE_DIR / "assets"
BACKGROUND_IMAGE_PATH = ASSETS_DIR / "mb_bg.png"
TRANSPARENT_COLOR = "#010203"


def load_discord_rpc_config() -> dict[str, str]:
    default_config = {
        "app_display_name": "SGMEditor",
        "client_id": "1494029959981830144",
        "large_image_key": "sgmeditor",
        "small_image_key": "sgmeditor_small",
    }

    config_path = DISCORD_RPC_PATH
    if config_path.is_dir():
        config_path = config_path / "config.json"

    if not config_path.exists():
        return default_config

    try:
        raw_config = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default_config

    merged_config = default_config.copy()
    for key in default_config:
        value = raw_config.get(key)
        if isinstance(value, str) and value.strip():
            merged_config[key] = value.strip()
    return merged_config


DISCORD_RPC_CONFIG = load_discord_rpc_config()
APP_DISPLAY_NAME = DISCORD_RPC_CONFIG["app_display_name"]
DISCORD_RPC_CLIENT_ID = DISCORD_RPC_CONFIG["client_id"]
DISCORD_LARGE_IMAGE_KEY = DISCORD_RPC_CONFIG["large_image_key"]
DISCORD_SMALL_IMAGE_KEY = DISCORD_RPC_CONFIG["small_image_key"]


@dataclass
class SearchHit:
    path: Path
    line_no: int
    line_text: str


class EditorTab:
    def __init__(self, app: "ModEditorApp", path: Path | None = None, content: str = ""):
        self.app = app
        self.path = path
        self.dirty = False
        self.frame = ttk.Frame(app.editor_notebook)
        self.text = ScrolledText(
            self.frame,
            undo=True,
            wrap="none",
            font=("Cascadia Mono", 11),
            tabs=("1c", "4c", "7c"),
            bg="#111a24",
            fg="#f3f1e8",
            insertbackground="#f3f1e8",
            selectbackground="#355a7a",
            selectforeground="#ffffff",
            borderwidth=0,
            highlightthickness=0,
        )
        self.text.pack(fill="both", expand=True)
        self.text.insert("1.0", content)
        self.text.edit_reset()
        self.text.bind("<<Modified>>", self._on_modified)
        self.text.bind("<KeyRelease>", self._sync_auxiliary_views)
        self.text.bind("<ButtonRelease>", self._sync_auxiliary_views)
        self.text.bind("<Control-s>", lambda event: self.app.save_current_file())

    @property
    def title(self) -> str:
        base = self.path.name if self.path else "Untitled"
        return f"*{base}" if self.dirty else base

    def _on_modified(self, _event=None):
        if self.text.edit_modified():
            self.dirty = True
            self.text.edit_modified(False)
            self.app.refresh_tab_titles()
            self._sync_auxiliary_views()

    def _sync_auxiliary_views(self, _event=None):
        if self.app.current_tab() is self:
            self.app.update_cursor_status()
            self.app.refresh_outline()

    def get_content(self) -> str:
        return self.text.get("1.0", "end-1c")


class DiscordPresenceManager:
    def __init__(self, client_id: str, large_image_key: str, small_image_key: str):
        self.client_id = client_id
        self.large_image_key = large_image_key
        self.small_image_key = small_image_key
        self.rpc = None
        self.connected = False
        self.started_at = int(time.time())
        self.last_payload: tuple[str, str] | None = None
        self.last_error: str = ""

    @property
    def available(self) -> bool:
        return Presence is not None and bool(self.client_id)

    def connect(self):
        if not self.available or self.connected:
            return
        try:
            self.rpc = Presence(self.client_id)
            self.rpc.connect()
            self.connected = True
            self.last_error = ""
        except Exception:
            self.rpc = None
            self.connected = False
            self.last_error = "Could not connect to Discord. Make sure the Discord desktop app is running."

    def update(self, project_name: str, file_name: str):
        if not self.available:
            return
        self.last_payload = (project_name, file_name)
        if not self.connected:
            self.connect()
        if not self.connected or self.rpc is None:
            return
        try:
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

            self.rpc.update(
                **payload,
            )
            self.last_error = ""
        except Exception:
            self.connected = False
            self.rpc = None
            self.last_error = "Discord RPC update failed. The editor will retry automatically."

    def ensure(self):
        if not self.available or self.connected or self.last_payload is None:
            return
        project_name, file_name = self.last_payload
        self.update(project_name, file_name)

    def clear(self):
        if not self.connected or self.rpc is None:
            return
        try:
            self.rpc.clear()
            self.rpc.close()
        except Exception:
            pass
        finally:
            self.connected = False
            self.rpc = None


class ModEditorApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_DISPLAY_NAME)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.overrideredirect(True)
        self.root.configure(bg=TRANSPARENT_COLOR)
        try:
            self.root.wm_attributes("-transparentcolor", TRANSPARENT_COLOR)
        except tk.TclError:
            pass

        self.project_dir: Path | None = None
        self.tree_paths: dict[str, Path] = {}
        self.tabs: list[EditorTab] = []
        self.discord_presence = DiscordPresenceManager(
            DISCORD_RPC_CLIENT_ID,
            DISCORD_LARGE_IMAGE_KEY,
            DISCORD_SMALL_IMAGE_KEY,
        )
        self.background_source = None
        self.background_photo = None
        self.background_label = None
        self.background_canvas = None
        self.background_image_id = None
        self.overlay_frame = None
        self.window_shell = None
        self.editor_header_var = tk.StringVar(value="# no file selected")
        self.drag_origin_x = 0
        self.drag_origin_y = 0
        self.ui_images: dict[str, tk.PhotoImage] = {}

        self.status_var = tk.StringVar(value="No project selected")
        self.search_var = tk.StringVar()

        self._build_background()
        self._load_ui_assets()
        self._build_style()
        self._build_menu()
        self._build_layout()
        self.root.bind("<Map>", lambda event: self._restore_borderless_window())
        self.update_discord_presence()
        self._schedule_discord_presence_retry()

    def _build_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(".", background="#090909", foreground="#e6ece8", fieldbackground="#090909")
        style.configure("Treeview", rowheight=22, background="#090909", foreground="#d7d7d7", fieldbackground="#090909", borderwidth=0, relief="flat")
        style.map("Treeview", background=[("selected", "#10292b")], foreground=[("selected", "#55f6ef")])
        style.configure("TNotebook", background="#090909", borderwidth=0, tabmargins=(0, 0, 0, 0))
        style.configure("TNotebook.Tab", background="#090909", foreground="#8f9a97", padding=(10, 4), borderwidth=0)
        style.map("TNotebook.Tab", background=[("selected", "#090909")], foreground=[("selected", "#56f4ee")])
        style.configure("Accent.TButton", padding=(8, 4), background="#090909", foreground="#56f4ee", borderwidth=0)
        style.map("Accent.TButton", background=[("active", "#10292b")])
        style.configure("TButton", padding=(8, 4), background="#090909", foreground="#cfd6d2", borderwidth=0)
        style.map("TButton", background=[("active", "#101414")], foreground=[("active", "#56f4ee")])
        style.configure("TEntry", fieldbackground="#090909", foreground="#dfe3df", insertcolor="#56f4ee", borderwidth=0)

    def _load_ui_assets(self):
        for name in (
            "exit_btn_clicked.png",
            "exit_btn_idle.png",
            "exit_btn_onmouse.png",
            "file_choose.png",
            "file_choose_last.png",
            "hide_btn_clicked.png",
            "hide_btn_idle.png",
            "hide_btn_onmouse.png",
            "me_logo.png",
            "sgme_logo.png",
        ):
            path = ASSETS_DIR / name
            if path.exists():
                self.ui_images[name] = tk.PhotoImage(file=str(path))

    def _build_background(self):
        if BACKGROUND_IMAGE_PATH.exists() and Image is not None and ImageTk is not None:
            self.background_source = Image.open(BACKGROUND_IMAGE_PATH).convert("RGBA")
            bbox = self.background_source.getbbox() or (0, 0, self.background_source.width, self.background_source.height)
            self.background_source = self.background_source.crop(bbox)
            self.root.geometry(f"{self.background_source.width}x{self.background_source.height}+90+40")
            self.root.minsize(self.background_source.width, self.background_source.height)
        else:
            self.root.geometry("1440x900+90+40")
            self.root.minsize(1180, 760)

        self.background_canvas = tk.Canvas(
            self.root,
            bg=TRANSPARENT_COLOR,
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
        )
        self.background_canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.background_image_id = self.background_canvas.create_image(0, 0, anchor="nw")

        self.overlay_frame = tk.Frame(self.root, bg=TRANSPARENT_COLOR, borderwidth=0, highlightthickness=0)
        self.overlay_frame.place(x=0, y=0, relwidth=1, relheight=1)
        self.root.bind("<Configure>", self._on_root_resize)
        self.root.bind("<Control-s>", lambda event: self.save_current_file())
        self.root.bind("<Escape>", lambda event: self.on_close())
        self._refresh_background()

    def _build_menu(self):
        return

    def _build_layout(self):
        self.window_shell = tk.Frame(self.overlay_frame, bg=TRANSPARENT_COLOR, bd=0, highlightthickness=0, relief="flat")
        self.window_shell.place(relx=0, rely=0, relwidth=1, relheight=1)

        topbar = tk.Frame(self.window_shell, bg=TRANSPARENT_COLOR, height=38, bd=0, highlightthickness=0, relief="flat")
        topbar.place(relx=0.06, rely=0.01, relwidth=0.88, height=38)
        topbar.pack_propagate(False)
        topbar.bind("<ButtonPress-1>", self._start_window_drag)
        topbar.bind("<B1-Motion>", self._perform_window_drag)

        menu_left = tk.Frame(topbar, bg=TRANSPARENT_COLOR, bd=0, highlightthickness=0, relief="flat")
        menu_left.pack(side="left", padx=(12, 0))
        for label, command in (("Project", self.open_project), ("File", self.save_current_file), ("Settings", self.export_zip)):
            button = tk.Label(menu_left, text=label, bg=TRANSPARENT_COLOR, fg="#d3d7d5", font=("Segoe UI", 9), cursor="hand2")
            button.pack(side="left", padx=(0, 10), pady=8)
            button.bind("<Button-1>", lambda event, callback=command: callback())
            button.bind("<Enter>", lambda event, widget=button: widget.config(fg="#56f4ee"))
            button.bind("<Leave>", lambda event, widget=button: widget.config(fg="#d3d7d5"))

        title_wrap = tk.Frame(topbar, bg=TRANSPARENT_COLOR, bd=0, highlightthickness=0, relief="flat")
        title_wrap.pack(side="top", pady=(4, 0))
        title_widgets = []
        logo_image = self.ui_images.get("me_logo.png")
        if logo_image is not None:
            logo_label = tk.Label(title_wrap, image=logo_image, bg=TRANSPARENT_COLOR, bd=0, highlightthickness=0)
            logo_label.pack(side="left", padx=(0, 10))
            title_widgets.append(logo_label)
        left_line = tk.Label(title_wrap, text="────", bg=TRANSPARENT_COLOR, fg="#2ed8d0", font=("Cascadia Mono", 13))
        title_label = tk.Label(title_wrap, text="MOD EDITOR", bg=TRANSPARENT_COLOR, fg="#2ef4ef", font=("Segoe UI", 14, "bold"))
        right_line = tk.Label(title_wrap, text="────", bg=TRANSPARENT_COLOR, fg="#2ed8d0", font=("Cascadia Mono", 13))
        left_line.pack(side="left")
        title_label.pack(side="left", padx=8)
        right_line.pack(side="left")
        title_widgets.extend((left_line, title_label, right_line))
        for widget in title_widgets:
            widget.bind("<ButtonPress-1>", self._start_window_drag)
            widget.bind("<B1-Motion>", self._perform_window_drag)

        control_wrap = tk.Frame(topbar, bg=TRANSPARENT_COLOR, bd=0, highlightthickness=0, relief="flat")
        control_wrap.pack(side="right", padx=(0, 6))
        minimize_label = tk.Label(
            control_wrap,
            image=self.ui_images.get("hide_btn_idle.png"),
            bg=TRANSPARENT_COLOR,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        minimize_label.pack(side="left", padx=(0, 10), pady=(6, 0))
        minimize_label.bind("<Button-1>", lambda event: self._minimize_window())
        minimize_label.bind("<ButtonPress-1>", lambda event: self._swap_label_image(minimize_label, "hide_btn_clicked.png"))
        minimize_label.bind("<ButtonRelease-1>", lambda event: self._swap_label_image(minimize_label, "hide_btn_onmouse.png"))
        minimize_label.bind("<Enter>", lambda event: self._swap_label_image(minimize_label, "hide_btn_onmouse.png"))
        minimize_label.bind("<Leave>", lambda event: self._swap_label_image(minimize_label, "hide_btn_idle.png"))

        close_label = tk.Label(
            control_wrap,
            image=self.ui_images.get("exit_btn_idle.png"),
            bg=TRANSPARENT_COLOR,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        close_label.pack(side="left")
        close_label.bind("<Button-1>", lambda event: self.on_close())
        close_label.bind("<ButtonPress-1>", lambda event: self._swap_label_image(close_label, "exit_btn_clicked.png"))
        close_label.bind("<ButtonRelease-1>", lambda event: self._swap_label_image(close_label, "exit_btn_onmouse.png"))
        close_label.bind("<Enter>", lambda event: self._swap_label_image(close_label, "exit_btn_onmouse.png"))
        close_label.bind("<Leave>", lambda event: self._swap_label_image(close_label, "exit_btn_idle.png"))

        body = tk.Frame(self.window_shell, bg=TRANSPARENT_COLOR, bd=0, highlightthickness=0, relief="flat")
        body.place(relx=0.06, rely=0.06, relwidth=0.88, relheight=0.86)
        body.grid_columnconfigure(0, weight=8)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(1, weight=1)
        body.grid_rowconfigure(2, weight=0)

        editor_header = tk.Frame(body, bg=TRANSPARENT_COLOR, bd=0, highlightthickness=0, relief="flat")
        editor_header.grid(row=0, column=0, sticky="ew", padx=(10, 0), pady=(6, 0))
        tk.Label(editor_header, textvariable=self.editor_header_var, bg=TRANSPARENT_COLOR, fg="#4ce4df", font=("Cascadia Mono", 10)).pack(side="left")
        search_entry = ttk.Entry(editor_header, textvariable=self.search_var, width=26)
        search_entry.pack(side="right", padx=(8, 0))
        search_entry.bind("<Return>", lambda event: self.run_project_search())
        open_project_label = tk.Label(
            editor_header,
            image=self.ui_images.get("file_choose.png"),
            bg=TRANSPARENT_COLOR,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        open_project_label.pack(side="right", padx=(12, 0))
        open_project_label.bind("<Button-1>", lambda event: self.open_project())
        open_project_label.bind("<Enter>", lambda event: self._swap_label_image(open_project_label, "file_choose_last.png"))
        open_project_label.bind("<Leave>", lambda event: self._swap_label_image(open_project_label, "file_choose.png"))
        ttk.Button(editor_header, text="Find", command=self.run_project_search, style="Accent.TButton").pack(side="right")

        self.editor_notebook = ttk.Notebook(body)
        self.editor_notebook.grid(row=1, column=0, sticky="nsew", padx=(10, 0), pady=(4, 0))
        self.editor_notebook.bind("<<NotebookTabChanged>>", lambda event: self._on_tab_changed())

        right_panel = tk.Frame(
            body,
            bg=TRANSPARENT_COLOR,
            width=180,
            highlightbackground=TRANSPARENT_COLOR,
            highlightcolor=TRANSPARENT_COLOR,
            highlightthickness=0,
            bd=0,
            relief="flat",
        )
        right_panel.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(10, 10), pady=(6, 0))
        right_panel.grid_propagate(False)
        tk.Label(right_panel, text="Project Files", bg=TRANSPARENT_COLOR, fg="#d7d9d7", font=("Segoe UI", 9)).pack(anchor="e", padx=10, pady=(6, 2))
        self.project_tree = ttk.Treeview(right_panel, show="tree")
        self.project_tree.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.project_tree.bind("<<TreeviewOpen>>", lambda event: self._populate_tree_children(self.project_tree.focus()))
        self.project_tree.bind("<Double-1>", self._open_selected_tree_item)

        bottom_panel = tk.Frame(body, bg=TRANSPARENT_COLOR, height=118, bd=0, highlightthickness=0, relief="flat")
        bottom_panel.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=(6, 8))
        bottom_panel.grid_propagate(False)
        tk.Label(bottom_panel, text="Search Results", bg=TRANSPARENT_COLOR, fg="#707a77", font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 3))
        self.search_results = ttk.Treeview(bottom_panel, columns=("file", "line", "text"), show="headings", height=4)
        self.search_results.heading("file", text="File")
        self.search_results.heading("line", text="Line")
        self.search_results.heading("text", text="Text")
        self.search_results.column("file", width=240, anchor="w")
        self.search_results.column("line", width=55, anchor="center")
        self.search_results.column("text", width=780, anchor="w")
        self.search_results.pack(fill="x")
        self.search_results.bind("<Double-1>", self._open_search_hit)

        status_bar = tk.Frame(self.window_shell, bg=TRANSPARENT_COLOR, height=18, bd=0, highlightthickness=0, relief="flat")
        status_bar.place(relx=0.06, rely=0.93, relwidth=0.88, height=18)
        status_bar.pack_propagate(False)
        self.mode_label = tk.Label(status_bar, text="Mode: No project open", anchor="w", bg=TRANSPARENT_COLOR, fg="#d7d9d7", font=("Segoe UI", 7))
        self.mode_label.pack(side="left", padx=6)
        self.cursor_label = tk.Label(status_bar, text="", anchor="center", bg=TRANSPARENT_COLOR, fg="#7a8481", font=("Segoe UI", 7))
        self.cursor_label.pack(side="right", padx=8)

    def _on_root_resize(self, _event=None):
        self._refresh_background()

    def _refresh_background(self):
        if self.background_source is None or Image is None or ImageTk is None:
            return

        width = max(self.root.winfo_width(), 1)
        height = max(self.root.winfo_height(), 1)
        resized = self.background_source.resize((width, height), Image.Resampling.LANCZOS)
        self.background_photo = ImageTk.PhotoImage(resized)
        if self.background_canvas is not None and self.background_image_id is not None:
            self.background_canvas.config(width=width, height=height)
            self.background_canvas.itemconfigure(self.background_image_id, image=self.background_photo)

    def _start_window_drag(self, event):
        self.drag_origin_x = event.x_root - self.root.winfo_x()
        self.drag_origin_y = event.y_root - self.root.winfo_y()

    def _perform_window_drag(self, event):
        x = event.x_root - self.drag_origin_x
        y = event.y_root - self.drag_origin_y
        self.root.geometry(f"+{x}+{y}")

    def _minimize_window(self):
        self.root.overrideredirect(False)
        self.root.iconify()
        self.root.after(200, self._restore_borderless_window)

    def _restore_borderless_window(self):
        if self.root.state() == "normal":
            self.root.overrideredirect(True)

    def _swap_label_image(self, label: tk.Label, asset_name: str):
        image = self.ui_images.get(asset_name)
        if image is not None:
            label.config(image=image)

    def create_mod_project(self):
        target = filedialog.askdirectory(title="Choose folder for the new mod project")
        if not target:
            return

        mod_title = simpledialog.askstring("Mod title", "Name of your mod:", parent=self.root)
        if not mod_title:
            return

        mod_id = simpledialog.askstring("Mod ID", "Internal mod ID (latin letters, digits, underscore):", parent=self.root)
        if not mod_id:
            return

        author = simpledialog.askstring("Author", "Author name:", parent=self.root) or "Unknown"
        version = simpledialog.askstring("Version", "Starting version:", parent=self.root) or "0.1.0"

        project_dir = Path(target) / mod_id
        project_dir.mkdir(parents=True, exist_ok=True)

        directories = [
            project_dir / "game" / mod_id,
            project_dir / "images",
            project_dir / "audio",
            project_dir / "docs",
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

        mod_info = {
            "id": mod_id,
            "title": mod_title,
            "author": author,
            "version": version,
            "game": "Love Money Rock'n'Roll",
            "engine": "Ren'Py",
            "entry_script": f"game/{mod_id}/script.rpy",
            "notes": "Generated by LMR Mod Editor",
        }

        script_content = (
            f'# {mod_title}\n'
            f'# Entry point for the mod "{mod_id}"\n\n'
            f'label {mod_id}_start:\n'
            f'    "Your mod is ready. Replace this scene with your story."\n'
            f'    return\n'
        )

        readme_content = (
            f"# {mod_title}\n\n"
            f"- Game: Love Money Rock'n'Roll\n"
            f"- Engine: Ren'Py\n"
            f"- Mod ID: `{mod_id}`\n"
            f"- Entry script: `game/{mod_id}/script.rpy`\n\n"
            "## Structure\n\n"
            "- `game/` - Ren'Py scripts\n"
            "- `images/` - custom CGs and sprites\n"
            "- `audio/` - music and SFX\n"
            "- `docs/` - design notes, TODO, references\n"
        )

        (project_dir / "mod_info.json").write_text(json.dumps(mod_info, ensure_ascii=False, indent=2), encoding="utf-8")
        (project_dir / "game" / mod_id / "script.rpy").write_text(script_content, encoding="utf-8")
        (project_dir / "README.md").write_text(readme_content, encoding="utf-8")

        self.open_project(project_dir)
        self.open_file(project_dir / "game" / mod_id / "script.rpy")
        self.status_var.set(f"Created mod project: {project_dir}")
        self.update_discord_presence()

    def open_project(self, chosen_path: Path | None = None):
        if chosen_path is None:
            folder = filedialog.askdirectory(title="Select mod project folder")
            if not folder:
                return
            chosen_path = Path(folder)

        self.project_dir = Path(chosen_path)
        self.reload_project_tree()
        self.root.title(f"{APP_DISPLAY_NAME} - {self.project_dir}")
        self.status_var.set(f"Opened project: {self.project_dir}")
        self.update_discord_presence()

    def reload_project_tree(self):
        self.project_tree.delete(*self.project_tree.get_children())
        self.tree_paths.clear()
        if not self.project_dir or not self.project_dir.exists():
            return

        root_id = self.project_tree.insert("", "end", text=self.project_dir.name, open=True)
        self.tree_paths[root_id] = self.project_dir
        self._add_tree_placeholders(root_id, self.project_dir)
        self._populate_tree_children(root_id)

    def _add_tree_placeholders(self, parent_id: str, folder: Path):
        if any(folder.iterdir()):
            placeholder = self.project_tree.insert(parent_id, "end", text="loading...")
            self.tree_paths[placeholder] = folder

    def _populate_tree_children(self, item_id: str):
        if item_id not in self.tree_paths:
            return

        path = self.tree_paths[item_id]
        existing_children = self.project_tree.get_children(item_id)
        if existing_children and self.project_tree.item(existing_children[0], "text") != "loading...":
            return

        for child in existing_children:
            self.project_tree.delete(child)

        if not path.is_dir():
            return

        entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        for entry in entries:
            child_id = self.project_tree.insert(item_id, "end", text=entry.name, open=False)
            self.tree_paths[child_id] = entry
            if entry.is_dir():
                self._add_tree_placeholders(child_id, entry)

    def _open_selected_tree_item(self, _event=None):
        selected = self.project_tree.focus()
        path = self.tree_paths.get(selected)
        if not path or path.is_dir():
            return
        self.open_file(path)

    def current_tab(self) -> EditorTab | None:
        if not self.tabs:
            return None
        current_widget = self.editor_notebook.select()
        for tab in self.tabs:
            if str(tab.frame) == current_widget:
                return tab
        return None

    def open_file(self, path: Path):
        path = Path(path)
        for index, tab in enumerate(self.tabs):
            if tab.path == path:
                self.editor_notebook.select(index)
                self.editor_header_var.set(f"# {path.name}")
                self.update_discord_presence()
                return

        if path.suffix.lower() not in TEXT_EXTENSIONS:
            messagebox.showinfo("Unsupported file", f"Preview/edit is enabled only for text files.\n\n{path.name}")
            return

        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = path.read_text(encoding="utf-8", errors="replace")

        tab = EditorTab(self, path=path, content=content)
        self.tabs.append(tab)
        self.editor_notebook.add(tab.frame, text=tab.title)
        self.editor_notebook.select(tab.frame)
        self.editor_header_var.set(f"# {path.name}")
        self.status_var.set(f"Opened file: {path}")
        self.update_cursor_status()
        self.update_discord_presence()

    def refresh_tab_titles(self):
        for index, tab in enumerate(self.tabs):
            self.editor_notebook.tab(index, text=tab.title)

    def save_current_file(self):
        tab = self.current_tab()
        if not tab:
            return False

        if tab.path is None:
            return self.save_current_file_as()

        tab.path.write_text(tab.get_content(), encoding="utf-8")
        tab.dirty = False
        self.refresh_tab_titles()
        self.status_var.set(f"Saved: {tab.path}")
        self.reload_project_tree()
        return True

    def save_current_file_as(self):
        tab = self.current_tab()
        if not tab:
            return False

        destination = filedialog.asksaveasfilename(
            title="Save file as",
            initialdir=str(self.project_dir or Path.cwd()),
            initialfile=tab.path.name if tab.path else "script.rpy",
            defaultextension=".rpy",
        )
        if not destination:
            return False

        tab.path = Path(destination)
        tab.path.write_text(tab.get_content(), encoding="utf-8")
        tab.dirty = False
        self.refresh_tab_titles()
        self.reload_project_tree()
        self.status_var.set(f"Saved as: {tab.path}")
        self.update_discord_presence()
        return True

    def export_zip(self):
        if not self.project_dir:
            messagebox.showwarning("No project", "Open or create a project first.")
            return

        output_base = filedialog.asksaveasfilename(
            title="Export ZIP archive",
            initialdir=str(self.project_dir.parent),
            initialfile=self.project_dir.name,
            defaultextension=".zip",
            filetypes=[("ZIP archive", "*.zip")],
        )
        if not output_base:
            return

        archive_base = str(Path(output_base).with_suffix(""))
        shutil.make_archive(archive_base, "zip", root_dir=self.project_dir)
        self.status_var.set(f"Archive exported: {archive_base}.zip")
        messagebox.showinfo("Export complete", f"Project archived to:\n{archive_base}.zip")

    def run_project_search(self):
        if not self.project_dir:
            messagebox.showwarning("No project", "Open or create a project first.")
            return

        query = self.search_var.get().strip()
        if not query:
            messagebox.showinfo("Search", "Enter text to search across the project.")
            return

        self.search_results.delete(*self.search_results.get_children())
        hit_count = 0

        for file_path in self.project_dir.rglob("*"):
            if not file_path.is_file() or file_path.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            try:
                lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for index, line in enumerate(lines, start=1):
                if query.lower() in line.lower():
                    values = (str(file_path.relative_to(self.project_dir)), index, line.strip())
                    item_id = self.search_results.insert("", "end", values=values)
                    self.search_results.set(item_id, "file", values[0])
                    hit_count += 1

        self.status_var.set(f"Search complete: {hit_count} matches for '{query}'")

    def _open_search_hit(self, _event=None):
        selected = self.search_results.focus()
        if not selected or not self.project_dir:
            return

        relative_path = self.search_results.item(selected, "values")[0]
        line_no = int(self.search_results.item(selected, "values")[1])
        self.open_file(self.project_dir / relative_path)
        tab = self.current_tab()
        if tab:
            tab.text.mark_set("insert", f"{line_no}.0")
            tab.text.see(f"{line_no}.0")
            tab.text.focus_set()
            self.update_cursor_status()

    def insert_selected_snippet(self):
        tab = self.current_tab()
        if not tab:
            messagebox.showinfo("No file open", "Open a script file before inserting a snippet.")
            return
        snippet_name = next(iter(SNIPPETS))
        tab.text.insert("insert", SNIPPETS[snippet_name])
        tab.text.focus_set()

    def refresh_outline(self):
        return

    def jump_to_outline_item(self, _event=None):
        return

    def update_cursor_status(self):
        tab = self.current_tab()
        if not tab:
            self.mode_label.config(text=f"Mode: {self.project_dir.name}" if self.project_dir else "Mode: No project open")
            self.cursor_label.config(text="")
            return

        cursor = tab.text.index("insert")
        line, column = cursor.split(".")
        current_file = tab.path.name if tab.path else "Untitled"
        self.mode_label.config(text=f"Mode: {self.project_dir.name}" if self.project_dir else "Mode: No project open")
        self.cursor_label.config(text=f"{current_file}   String: {line}   Column: {column}")
        self.status_var.set(f"{current_file} | Line {line}, Column {column}")

    def _on_tab_changed(self):
        current_tab = self.current_tab()
        self.editor_header_var.set(f"# {current_tab.path.name}" if current_tab and current_tab.path else "# no file selected")
        self.update_cursor_status()
        self.update_discord_presence()

    def update_discord_presence(self):
        project_name = self.project_dir.name if self.project_dir else "No project open"
        current_tab = self.current_tab()
        file_name = current_tab.path.name if current_tab and current_tab.path else "No file open"
        self.discord_presence.update(project_name=project_name, file_name=file_name)

    def _schedule_discord_presence_retry(self):
        self.discord_presence.ensure()
        self.root.after(15000, self._schedule_discord_presence_retry)

    def maybe_save_dirty_tabs(self) -> bool:
        dirty_tabs = [tab for tab in self.tabs if tab.dirty]
        if not dirty_tabs:
            return True

        answer = messagebox.askyesnocancel(
            "Unsaved changes",
            f"You have {len(dirty_tabs)} unsaved file(s). Save before closing?",
        )
        if answer is None:
            return False
        if answer:
            for tab in dirty_tabs:
                self.editor_notebook.select(tab.frame)
                if not self.save_current_file():
                    return False
        return True

    def on_close(self):
        if self.maybe_save_dirty_tabs():
            self.discord_presence.clear()
            self.root.destroy()


def main():
    root = tk.Tk()
    app = ModEditorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
