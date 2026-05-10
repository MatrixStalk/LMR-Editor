import ctypes
import json
import sys
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QFileSystemWatcher,
    QObject,
    QPoint,
    QPropertyAnimation,
    QRectF,
    QTimer,
    Qt,
)
from PySide6.QtGui import QColor, QIcon, QMouseEvent, QPainterPath, QPixmap, QRegion
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .theme import APP_QSS, BLUE_SOFT, NEON, NEON_2, STYLE_PATH, load_app_qss


BASE_DIR = Path(__file__).resolve().parents[2]
APP_ICON_PATH = BASE_DIR / "icon.ico"
TRAY_ICON_PATH = BASE_DIR / "assets" / "tray_icon.png"
LAYOUT_PATH = Path(__file__).with_name("live_layout.json")
DWMWA_BORDER_COLOR = 34
DWMWA_CAPTION_COLOR = 35
DWMWA_NCRENDERING_POLICY = 2
DWMWA_SYSTEMBACKDROP_TYPE = 38
DWMWA_TEXT_COLOR = 36
DWMWA_WINDOW_CORNER_PREFERENCE = 33
DWORD = ctypes.c_uint
DWMNCRP_DISABLED = 1
DWMWCP_DONOTROUND = 1
DWM_COLOR_NONE = 0xFFFFFFFE
DWMSBT_NONE = 1
GWL_STYLE = -16
GCL_STYLE = -26
SWP_FRAMECHANGED = 0x0020
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_POPUP = 0x80000000
CS_DROPSHADOW = 0x00020000


def glow(widget: QWidget, color: str = NEON, blur: int = 26, alpha: int = 255) -> None:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, 0)
    qcolor = QColor(color)
    qcolor.setAlpha(max(0, min(255, int(alpha))))
    effect.setColor(qcolor)
    widget.setGraphicsEffect(effect)


def read_layout_config() -> dict:
    default = {
        "window": {
            "width": 1280,
            "height": 760,
            "min_width": 760,
            "min_height": 460,
            "outer_radius": 30,
            "resize_margin": 10,
        },
        "layers": {
            "root_margins": [14, 14, 14, 14],
            "backdrop_margins": [14, 14, 14, 14],
            "shell_margins": [18, 10, 18, 14],
        },
        "chrome": {
            "height": 90,
            "margins": [28, 14, 18, 8],
            "spacing": 16,
            "title_spacing": 2,
            "logo_size": 70,
        },
        "effects": {
            "shell_glow_blur": 26,
            "shell_glow_alpha": 255,
            "backdrop_blur_blur": 36,
            "backdrop_blur_alpha": 210,
        },
    }
    try:
        loaded = json.loads(LAYOUT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    return merge_layout(default, loaded)


def merge_layout(default: dict, loaded: dict) -> dict:
    result = dict(default)
    for key, value in loaded.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_layout(result[key], value)
        else:
            result[key] = value
    return result


def margins(values: list[int]) -> tuple[int, int, int, int]:
    padded = [int(value) for value in values[:4]]
    padded.extend([0] * (4 - len(padded)))
    return tuple(padded[:4])


def remove_windows_frame_artifacts(window: QWidget) -> None:
    if sys.platform != "win32":
        return
    hwnd = int(window.winId())
    user32 = ctypes.windll.user32

    style = user32.GetWindowLongPtrW(hwnd, GWL_STYLE)
    style &= ~WS_CAPTION
    style &= ~WS_THICKFRAME
    style |= WS_POPUP
    user32.SetWindowLongPtrW(hwnd, GWL_STYLE, style)

    class_style = user32.GetClassLongPtrW(hwnd, GCL_STYLE)
    if class_style & CS_DROPSHADOW:
        user32.SetClassLongPtrW(hwnd, GCL_STYLE, class_style & ~CS_DROPSHADOW)

    user32.SetWindowPos(
        hwnd,
        0,
        0,
        0,
        0,
        0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED,
    )

    attributes = (
        (DWMWA_NCRENDERING_POLICY, DWORD(DWMNCRP_DISABLED)),
        (DWMWA_BORDER_COLOR, DWORD(DWM_COLOR_NONE)),
        (DWMWA_CAPTION_COLOR, DWORD(DWM_COLOR_NONE)),
        (DWMWA_TEXT_COLOR, DWORD(DWM_COLOR_NONE)),
        (DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.c_int(DWMWCP_DONOTROUND)),
        (DWMWA_SYSTEMBACKDROP_TYPE, DWORD(DWMSBT_NONE)),
    )
    for attribute, value in attributes:
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(hwnd),
            ctypes.c_uint(attribute),
            ctypes.byref(value),
            ctypes.sizeof(value),
        )


class ChromeBar(QFrame):
    def __init__(self, parent: "MenuWindow") -> None:
        super().__init__(parent)
        self.setObjectName("Chrome")

        self.layout = QHBoxLayout(self)

        self.logo = QLabel()
        if TRAY_ICON_PATH.exists():
            self._logo_source = QPixmap(str(TRAY_ICON_PATH))
        else:
            self._logo_source = QPixmap()
        self.layout.addWidget(self.logo)

        self.title_box = QVBoxLayout()

        self.title = QLabel("MOD EDITOR")
        self.title.setObjectName("AppTitle")
        self.subtitle = QLabel("modern visual novel modding workspace")
        self.subtitle.setObjectName("AppSubtitle")

        self.title_box.addWidget(self.title)
        self.title_box.addWidget(self.subtitle)
        self.layout.addLayout(self.title_box)
        self.layout.addStretch(1)

        min_button = QPushButton("-")
        min_button.setObjectName("WindowButton")
        min_button.clicked.connect(parent.showMinimized)
        self.layout.addWidget(min_button)

        max_button = QPushButton("[]")
        max_button.setObjectName("WindowButton")
        max_button.clicked.connect(parent.toggle_maximized)
        self.layout.addWidget(max_button)

        close_button = QPushButton("x")
        close_button.setObjectName("WindowButton")
        close_button.setProperty("role", "danger")
        close_button.clicked.connect(parent.close)
        self.layout.addWidget(close_button)

        self._pulse_on = False
        self._pulse = QTimer(self)
        self._pulse.timeout.connect(self._pulse_title)
        self._pulse.start(1000)

    def apply_layout(self, config: dict) -> None:
        chrome = config["chrome"]
        logo_size = int(chrome["logo_size"])
        self.setFixedHeight(int(chrome["height"]))
        self.layout.setContentsMargins(*margins(chrome["margins"]))
        self.layout.setSpacing(int(chrome["spacing"]))
        self.title_box.setSpacing(int(chrome["title_spacing"]))
        self.logo.setFixedSize(logo_size, logo_size)
        if not self._logo_source.isNull():
            self.logo.setPixmap(
                self._logo_source.scaled(logo_size, logo_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )

    def _pulse_title(self) -> None:
        self._pulse_on = not self._pulse_on
        self.title.setStyleSheet(f"color: {NEON_2 if self._pulse_on else BLUE_SOFT};")


class MenuWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._layout_config = read_layout_config()
        self.setWindowTitle("Mod Editor - Main Menu Concept")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)
        if APP_ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(APP_ICON_PATH)))

        self._drag_offset: QPoint | None = None
        self._resize_edges: set[str] = set()
        self._resize_start_pos: QPoint | None = None
        self._resize_start_geometry = None
        self._live_reload_timer = QTimer(self)
        self._live_reload_timer.setSingleShot(True)
        self._live_reload_timer.timeout.connect(self._reload_live_files)
        self._live_watcher = QFileSystemWatcher(self)
        self._live_watcher.fileChanged.connect(self._schedule_live_reload)

        root = QWidget()
        root.setObjectName("Root")
        root.setMouseTracking(True)
        self.setCentralWidget(root)

        self.root_layout = QVBoxLayout(root)
        self.root_layout.setSpacing(0)

        self.backdrop = QFrame()
        self.backdrop.setObjectName("Backdrop")
        self.backdrop.setMouseTracking(True)
        self.root_layout.addWidget(self.backdrop)

        self.backdrop_layout = QVBoxLayout(self.backdrop)
        self.backdrop_layout.setSpacing(0)

        self.shell = QFrame()
        self.shell.setObjectName("Shell")
        self.shell.setMouseTracking(True)
        self.backdrop_layout.addWidget(self.shell)

        self.shell_layout = QVBoxLayout(self.shell)
        self.shell_layout.setSpacing(0)

        self.chrome = ChromeBar(self)
        self.shell_layout.addWidget(self.chrome)
        self.shell_layout.addStretch(1)
        self.apply_layout_config(initial=True)

        self._install_window_mouse_filters(root)

        self._apply_rounded_window_mask()
        self._watch_live_files()
        remove_windows_frame_artifacts(self)
        self._fade_in()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        remove_windows_frame_artifacts(self)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_rounded_window_mask()
        remove_windows_frame_artifacts(self)

    def _apply_rounded_window_mask(self) -> None:
        path = QPainterPath()
        radius = int(self._layout_config["window"]["outer_radius"])
        path.addRoundedRect(QRectF(0, 0, self.width(), self.height()), radius, radius)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def _watch_live_files(self) -> None:
        for path in (STYLE_PATH, str(LAYOUT_PATH)):
            if path not in self._live_watcher.files():
                self._live_watcher.addPath(path)

    def _schedule_live_reload(self) -> None:
        self._live_reload_timer.start(80)

    def _reload_live_files(self) -> None:
        self._watch_live_files()
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(load_app_qss())
        self._layout_config = read_layout_config()
        self.apply_layout_config(initial=False)

    def apply_layout_config(self, initial: bool = False) -> None:
        window = self._layout_config["window"]
        layers = self._layout_config["layers"]
        effects = self._layout_config["effects"]

        self.RESIZE_MARGIN = int(window["resize_margin"])
        self.setMinimumSize(int(window["min_width"]), int(window["min_height"]))
        if initial:
            self.resize(int(window["width"]), int(window["height"]))

        self.root_layout.setContentsMargins(*margins(layers["root_margins"]))
        self.backdrop_layout.setContentsMargins(*margins(layers["backdrop_margins"]))
        self.shell_layout.setContentsMargins(*margins(layers["shell_margins"]))
        self.chrome.apply_layout(self._layout_config)
        glow(
            self.backdrop,
            color="#000000",
            blur=int(effects["backdrop_blur_blur"]),
            alpha=int(effects["backdrop_blur_alpha"]),
        )
        glow(
            self.shell,
            blur=int(effects["shell_glow_blur"]),
            alpha=int(effects["shell_glow_alpha"]),
        )
        self._apply_rounded_window_mask()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if isinstance(watched, QPushButton):
            return False
        if event.type() == QEvent.MouseButtonPress:
            return self._handle_mouse_press(event)
        if event.type() == QEvent.MouseMove:
            return self._handle_mouse_move(event)
        if event.type() == QEvent.MouseButtonRelease:
            return self._handle_mouse_release(event)
        if event.type() == QEvent.Leave:
            if not self._drag_offset and not self._resize_edges:
                self.unsetCursor()
        return super().eventFilter(watched, event)

    def _install_window_mouse_filters(self, root: QWidget) -> None:
        for widget in [root, *root.findChildren(QWidget)]:
            if isinstance(widget, QPushButton):
                continue
            widget.setMouseTracking(True)
            widget.installEventFilter(self)

    def _handle_mouse_press(self, event: QMouseEvent) -> bool:
        if event.button() != Qt.LeftButton:
            return False

        edges = self._edges_at_global_pos(event.globalPosition().toPoint())
        if edges:
            self._resize_edges = edges
            self._resize_start_pos = event.globalPosition().toPoint()
            self._resize_start_geometry = self.geometry()
            return True

        self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        return True

    def _handle_mouse_move(self, event: QMouseEvent) -> bool:
        global_pos = event.globalPosition().toPoint()
        if self._resize_edges and self._resize_start_pos is not None and self._resize_start_geometry is not None:
            self._resize_window(global_pos)
            return True

        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(global_pos - self._drag_offset)
            return True

        self._update_cursor(global_pos)
        return False

    def _handle_mouse_release(self, event: QMouseEvent) -> bool:
        self._drag_offset = None
        self._resize_edges = set()
        self._resize_start_pos = None
        self._resize_start_geometry = None
        self._update_cursor(event.globalPosition().toPoint())
        return False

    def _edges_at_global_pos(self, global_pos: QPoint) -> set[str]:
        pos = self.mapFromGlobal(global_pos)
        rect = self.rect()
        edges = set()
        if pos.x() <= self.RESIZE_MARGIN:
            edges.add("left")
        if pos.x() >= rect.width() - self.RESIZE_MARGIN:
            edges.add("right")
        if pos.y() <= self.RESIZE_MARGIN:
            edges.add("top")
        if pos.y() >= rect.height() - self.RESIZE_MARGIN:
            edges.add("bottom")
        return edges

    def _update_cursor(self, global_pos: QPoint) -> None:
        edges = self._edges_at_global_pos(global_pos)
        if edges in ({"left", "top"}, {"right", "bottom"}):
            self.setCursor(Qt.SizeFDiagCursor)
        elif edges in ({"right", "top"}, {"left", "bottom"}):
            self.setCursor(Qt.SizeBDiagCursor)
        elif "left" in edges or "right" in edges:
            self.setCursor(Qt.SizeHorCursor)
        elif "top" in edges or "bottom" in edges:
            self.setCursor(Qt.SizeVerCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def _resize_window(self, global_pos: QPoint) -> None:
        delta = global_pos - self._resize_start_pos
        geometry = self._resize_start_geometry
        min_width = self.minimumWidth()
        min_height = self.minimumHeight()

        left = geometry.left()
        top = geometry.top()
        right = geometry.right()
        bottom = geometry.bottom()

        if "left" in self._resize_edges:
            left = min(left + delta.x(), right - min_width)
        if "right" in self._resize_edges:
            right = max(right + delta.x(), left + min_width)
        if "top" in self._resize_edges:
            top = min(top + delta.y(), bottom - min_height)
        if "bottom" in self._resize_edges:
            bottom = max(bottom + delta.y(), top + min_height)

        self.setGeometry(left, top, right - left + 1, bottom - top + 1)

    def _fade_in(self) -> None:
        self.setWindowOpacity(0.0)
        animation = QPropertyAnimation(self, b"windowOpacity", self)
        animation.setDuration(260)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.OutCubic)
        animation.start(QPropertyAnimation.DeleteWhenStopped)

    def toggle_maximized(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()


def run() -> None:
    app = QApplication(sys.argv)
    app.setStyleSheet(APP_QSS)
    window = MenuWindow()
    window.show()
    sys.exit(app.exec())
