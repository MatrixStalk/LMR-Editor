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

APP_DISPLAY_NAME = "Soviet Games Editor"
DISCORD_RPC_CLIENT_ID = os.environ.get("DISCORD_RPC_CLIENT_ID", "").strip()


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
            font=("Consolas", 11),
            tabs=("1c", "4c", "7c"),
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
    def __init__(self, client_id: str):
        self.client_id = client_id
        self.rpc = None
        self.connected = False
        self.started_at = int(time.time())

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
        except Exception:
            self.rpc = None
            self.connected = False

    def update(self, project_name: str, file_name: str):
        if not self.available:
            return
        if not self.connected:
            self.connect()
        if not self.connected or self.rpc is None:
            return
        try:
            self.rpc.update(
                details=project_name,
                state=file_name,
                large_text=APP_DISPLAY_NAME,
                start=self.started_at,
            )
        except Exception:
            self.connected = False
            self.rpc = None

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
        self.root.geometry("1440x900")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.project_dir: Path | None = None
        self.tree_paths: dict[str, Path] = {}
        self.tabs: list[EditorTab] = []
        self.discord_presence = DiscordPresenceManager(DISCORD_RPC_CLIENT_ID)

        self.status_var = tk.StringVar(value="No project selected")
        self.search_var = tk.StringVar()

        self._build_style()
        self._build_menu()
        self._build_layout()

    def _build_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", rowheight=24)
        style.configure("Accent.TButton", padding=(12, 8))

    def _build_menu(self):
        menu = tk.Menu(self.root)

        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="New Mod Project", command=self.create_mod_project)
        file_menu.add_command(label="Open Project Folder", command=self.open_project)
        file_menu.add_separator()
        file_menu.add_command(label="Save", command=self.save_current_file, accelerator="Ctrl+S")
        file_menu.add_command(label="Save As...", command=self.save_current_file_as)
        file_menu.add_separator()
        file_menu.add_command(label="Export Project as ZIP", command=self.export_zip)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)

        tools_menu = tk.Menu(menu, tearoff=False)
        tools_menu.add_command(label="Search In Project", command=self.run_project_search)
        tools_menu.add_command(label="Refresh File Tree", command=self.reload_project_tree)
        tools_menu.add_command(label="Insert Selected Snippet", command=self.insert_selected_snippet)

        menu.add_cascade(label="File", menu=file_menu)
        menu.add_cascade(label="Tools", menu=tools_menu)
        self.root.config(menu=menu)
        self.root.bind("<Control-s>", lambda event: self.save_current_file())

    def _build_layout(self):
        toolbar = ttk.Frame(self.root, padding=10)
        toolbar.pack(fill="x")

        ttk.Button(toolbar, text="New Mod", style="Accent.TButton", command=self.create_mod_project).pack(side="left")
        ttk.Button(toolbar, text="Open Folder", command=self.open_project).pack(side="left", padx=(8, 0))
        ttk.Button(toolbar, text="Save", command=self.save_current_file).pack(side="left", padx=(8, 0))
        ttk.Button(toolbar, text="Export ZIP", command=self.export_zip).pack(side="left", padx=(8, 0))

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=12)
        ttk.Label(toolbar, text="Search").pack(side="left")
        search_entry = ttk.Entry(toolbar, textvariable=self.search_var, width=32)
        search_entry.pack(side="left", padx=(8, 8))
        search_entry.bind("<Return>", lambda event: self.run_project_search())
        ttk.Button(toolbar, text="Find", command=self.run_project_search).pack(side="left")

        main_pane = ttk.Panedwindow(self.root, orient="horizontal")
        main_pane.pack(fill="both", expand=True)

        left_panel = ttk.Frame(main_pane, padding=(10, 0, 0, 10))
        center_panel = ttk.Frame(main_pane, padding=10)
        right_panel = ttk.Frame(main_pane, padding=(0, 0, 10, 10))
        main_pane.add(left_panel, weight=2)
        main_pane.add(center_panel, weight=5)
        main_pane.add(right_panel, weight=2)

        ttk.Label(left_panel, text="Project Files").pack(anchor="w", pady=(6, 6))
        self.project_tree = ttk.Treeview(left_panel, show="tree")
        self.project_tree.pack(fill="both", expand=True)
        self.project_tree.bind("<<TreeviewOpen>>", lambda event: self._populate_tree_children(self.project_tree.focus()))
        self.project_tree.bind("<Double-1>", self._open_selected_tree_item)

        ttk.Label(center_panel, text="Script Editor").pack(anchor="w", pady=(0, 6))
        self.editor_notebook = ttk.Notebook(center_panel)
        self.editor_notebook.pack(fill="both", expand=True)
        self.editor_notebook.bind("<<NotebookTabChanged>>", lambda event: self._on_tab_changed())

        bottom_panel = ttk.Frame(center_panel)
        bottom_panel.pack(fill="both", expand=False, pady=(10, 0))
        ttk.Label(bottom_panel, text="Search Results").pack(anchor="w", pady=(0, 4))
        self.search_results = ttk.Treeview(bottom_panel, columns=("file", "line", "text"), show="headings", height=8)
        self.search_results.heading("file", text="File")
        self.search_results.heading("line", text="Line")
        self.search_results.heading("text", text="Text")
        self.search_results.column("file", width=260, anchor="w")
        self.search_results.column("line", width=60, anchor="center")
        self.search_results.column("text", width=540, anchor="w")
        self.search_results.pack(fill="x")
        self.search_results.bind("<Double-1>", self._open_search_hit)

        ttk.Label(right_panel, text="Ren'Py Snippets").pack(anchor="w", pady=(6, 6))
        self.snippet_list = tk.Listbox(right_panel, height=10, exportselection=False)
        for name in SNIPPETS:
            self.snippet_list.insert("end", name)
        self.snippet_list.pack(fill="x")
        self.snippet_list.bind("<Double-1>", lambda event: self.insert_selected_snippet())

        ttk.Button(right_panel, text="Insert Snippet", command=self.insert_selected_snippet).pack(fill="x", pady=(8, 18))

        ttk.Label(right_panel, text="Current File Outline").pack(anchor="w", pady=(0, 6))
        self.outline_list = tk.Listbox(right_panel, height=14, exportselection=False)
        self.outline_list.pack(fill="both", expand=True)
        self.outline_list.bind("<Double-1>", self.jump_to_outline_item)

        status_bar = ttk.Label(self.root, textvariable=self.status_var, anchor="w", relief="sunken", padding=(10, 6))
        status_bar.pack(fill="x", side="bottom")

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
        self.status_var.set(f"Opened file: {path}")
        self.refresh_outline()
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

        selection = self.snippet_list.curselection()
        if not selection:
            messagebox.showinfo("Snippet", "Select a snippet first.")
            return

        snippet_name = self.snippet_list.get(selection[0])
        tab.text.insert("insert", SNIPPETS[snippet_name])
        tab.text.focus_set()

    def refresh_outline(self):
        self.outline_list.delete(0, "end")
        tab = self.current_tab()
        if not tab:
            return

        lines = tab.get_content().splitlines()
        for line_no, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("label ") and stripped.endswith(":"):
                self.outline_list.insert("end", f"{line_no}: {stripped}")
            elif stripped.startswith("screen ") and stripped.endswith(":"):
                self.outline_list.insert("end", f"{line_no}: {stripped}")
            elif stripped.startswith("menu:"):
                self.outline_list.insert("end", f"{line_no}: menu:")

    def jump_to_outline_item(self, _event=None):
        tab = self.current_tab()
        if not tab:
            return

        selection = self.outline_list.curselection()
        if not selection:
            return

        entry = self.outline_list.get(selection[0])
        line_no = entry.split(":", 1)[0]
        tab.text.mark_set("insert", f"{line_no}.0")
        tab.text.see(f"{line_no}.0")
        tab.text.focus_set()
        self.update_cursor_status()

    def update_cursor_status(self):
        tab = self.current_tab()
        if not tab:
            return

        cursor = tab.text.index("insert")
        line, column = cursor.split(".")
        project = str(self.project_dir) if self.project_dir else "No project"
        current_file = tab.path.name if tab.path else "Untitled"
        self.status_var.set(f"{project} | {current_file} | Line {line}, Column {column}")

    def _on_tab_changed(self):
        self.refresh_outline()
        self.update_cursor_status()
        self.update_discord_presence()

    def update_discord_presence(self):
        project_name = self.project_dir.name if self.project_dir else "No project open"
        current_tab = self.current_tab()
        file_name = current_tab.path.name if current_tab and current_tab.path else "No file open"
        self.discord_presence.update(project_name=project_name, file_name=file_name)

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
