import os
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QSizePolicy, QFrame
)
from qfluentwidgets import (
    LineEdit, TextEdit, ToolButton, TransparentToolButton,
    FluentIcon, CaptionLabel, StrongBodyLabel
)

from ok.device.linux_proton_launcher import get_proton_launcher


class ProtonLaunchWidget(QFrame):
    """Collapsible settings panel for Linux Proton/Wine launch parameters and container configuration."""

    expanded_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.launcher = get_proton_launcher()
        self._is_expanded = False

        self.setObjectName("protonLaunchCard")
        self.setStyleSheet("""
            #protonLaunchCard {
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 8px;
                background-color: rgba(255, 255, 255, 0.03);
            }
        """)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 8, 10, 8)
        self.main_layout.setSpacing(6)

        # 1. Header Row (Clickable toggle)
        self.header_widget = QWidget(self)
        self.header_widget.setCursor(Qt.PointingHandCursor)
        header_layout = QHBoxLayout(self.header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        self.header_icon = ToolButton(FluentIcon.GAME, self.header_widget)
        self.header_icon.setFixedSize(26, 26)
        self.header_icon.setEnabled(False)

        self.header_title = StrongBodyLabel(self.tr("Game Launch Options"), self.header_widget)
        self.header_title.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.toggle_btn = TransparentToolButton(FluentIcon.ARROW_DOWN, self.header_widget)
        self.toggle_btn.setFixedSize(26, 26)
        self.toggle_btn.clicked.connect(self.toggle_expanded)

        header_layout.addWidget(self.header_icon)
        header_layout.addWidget(self.header_title)
        header_layout.addWidget(self.toggle_btn)

        self.header_widget.mousePressEvent = lambda e: self.toggle_expanded()
        self.main_layout.addWidget(self.header_widget)

        # 2. Collapsible Content Container
        self.content_widget = QWidget(self)
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 4, 0, 0)
        self.content_layout.setSpacing(6)

        # Game Executable
        self.content_layout.addWidget(CaptionLabel(self.tr("Game Executable Path:")))
        exe_row = QHBoxLayout()
        exe_row.setSpacing(4)
        self.exe_edit = LineEdit(self.content_widget)
        self.exe_edit.setPlaceholderText(self.tr("Path to Client-Win64-Shipping.exe"))
        self.exe_browse_btn = TransparentToolButton(FluentIcon.FOLDER, self.content_widget)
        self.exe_browse_btn.clicked.connect(self._browse_exe)
        exe_row.addWidget(self.exe_edit)
        exe_row.addWidget(self.exe_browse_btn)
        self.content_layout.addLayout(exe_row)

        # Wine/Proton Prefix
        self.content_layout.addWidget(CaptionLabel(self.tr("Proton/Wine Prefix Directory:")))
        prefix_row = QHBoxLayout()
        prefix_row.setSpacing(4)
        self.prefix_edit = LineEdit(self.content_widget)
        self.prefix_edit.setPlaceholderText(self.tr("e.g. ~/Games/Pronton"))
        self.prefix_browse_btn = TransparentToolButton(FluentIcon.FOLDER, self.content_widget)
        self.prefix_browse_btn.clicked.connect(self._browse_prefix)
        prefix_row.addWidget(self.prefix_edit)
        prefix_row.addWidget(self.prefix_browse_btn)
        self.content_layout.addLayout(prefix_row)

        # Launch Arguments
        self.content_layout.addWidget(CaptionLabel(self.tr("Launch Arguments:")))
        self.args_edit = LineEdit(self.content_widget)
        self.args_edit.setPlaceholderText(self.tr("e.g. Client -dx12 -krqlv=hd"))
        self.content_layout.addWidget(self.args_edit)

        # Command Wrapper
        self.content_layout.addWidget(CaptionLabel(self.tr("Command Wrapper (Optional):")))
        self.wrapper_edit = LineEdit(self.content_widget)
        self.wrapper_edit.setPlaceholderText(self.tr("e.g. dlssg mangohud umu-run"))
        self.content_layout.addWidget(self.wrapper_edit)

        # Custom Environment Variables (Flexible vertical height)
        self.content_layout.addWidget(CaptionLabel(self.tr("Custom Environment Variables (KEY=VALUE):")))
        self.env_edit = TextEdit(self.content_widget)
        self.env_edit.setMinimumHeight(110)
        self.env_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.env_edit.setPlaceholderText("ANTI_DITHER_ENABLED=1\nDXVK_FRAME_RATE=90\nVKD3D_CONFIG=no_upload_hvv")
        self.content_layout.addWidget(self.env_edit, 1)

        self.main_layout.addWidget(self.content_widget, 1)

        # Connect signals for auto persistence
        self.exe_edit.editingFinished.connect(self.save_config)
        self.prefix_edit.editingFinished.connect(self.save_config)
        self.args_edit.editingFinished.connect(self.save_config)
        self.wrapper_edit.editingFinished.connect(self.save_config)
        self.env_edit.textChanged.connect(self.save_config)

        # Load persisted config and start collapsed
        self.load_config()
        self.set_expanded(False)

    def load_config(self):
        cfg = self.launcher.get_config()
        self.exe_edit.setText(cfg.get('game_exe', ''))
        self.prefix_edit.setText(cfg.get('wine_prefix', ''))
        self.args_edit.setText(cfg.get('launch_args', ''))
        self.wrapper_edit.setText(cfg.get('wrapper', ''))
        self.env_edit.setText(cfg.get('custom_env', ''))

    def save_config(self):
        self.launcher.update_config(
            game_exe=self.exe_edit.text().strip(),
            wine_prefix=self.prefix_edit.text().strip(),
            launch_args=self.args_edit.text().strip(),
            wrapper=self.wrapper_edit.text().strip(),
            custom_env=self.env_edit.toPlainText().strip(),
        )

    def set_expanded(self, expanded: bool):
        self._is_expanded = expanded
        self.content_widget.setVisible(expanded)
        self.toggle_btn.setIcon(FluentIcon.ARROW_UP if expanded else FluentIcon.ARROW_DOWN)
        if expanded:
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        else:
            self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.updateGeometry()
        self.expanded_changed.emit(expanded)

    def toggle_expanded(self):
        self.set_expanded(not self._is_expanded)

    def update_from_detected(self, data: dict):
        if not data:
            return
        if data.get('game_exe'):
            self.exe_edit.setText(data['game_exe'])
        if data.get('wine_prefix'):
            self.prefix_edit.setText(data['wine_prefix'])
        if data.get('launch_args'):
            self.args_edit.setText(data['launch_args'])
        if data.get('wrapper'):
            self.wrapper_edit.setText(data['wrapper'])
        if data.get('custom_env'):
            self.env_edit.setText(data['custom_env'])

        # Auto save and expand
        self.save_config()
        if data.get('runner_path'):
            self.launcher.update_config(runner_path=data['runner_path'])
        self.set_expanded(True)

    def _browse_exe(self):
        init_dir = os.path.dirname(self.exe_edit.text().strip()) if self.exe_edit.text().strip() else os.path.expanduser("~")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Select Game Executable"),
            init_dir,
            self.tr("Windows Executable (*.exe);;All Files (*)")
        )
        if file_path:
            self.exe_edit.setText(file_path)
            self.save_config()

    def _browse_prefix(self):
        init_dir = self.prefix_edit.text().strip() or os.path.expanduser("~")
        dir_path = QFileDialog.getExistingDirectory(
            self,
            self.tr("Select Proton/Wine Prefix Directory"),
            init_dir
        )
        if dir_path:
            self.prefix_edit.setText(dir_path)
            self.save_config()
