import os
import threading

from PySide6.QtCore import QEvent, QPoint, QTimer, QUrl, Signal, Qt
from PySide6.QtGui import QDesktopServices, QFontMetrics, QIcon, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget
from qfluentwidgets import Action, BodyLabel, ComboBox, FluentIcon, IndeterminateProgressRing, \
    PrimaryPushButton, PushButton, RoundMenu

from ok.util.git_updater import check_git_updates, get_local_commits, is_git_repository, pull_git_updates, restart_with_uv
from ok.util.logger import Logger


logger = Logger.get_logger(__name__)


def _is_numeric_version(version):
    try:
        return bool(version) and all(part.isdigit() for part in version.lstrip("v").split("."))
    except AttributeError:
        return False


class ChangeLogView(BodyLabel):
    """A non-interactive, word-wrapped changelog that follows its text height."""

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setWordWrap(True)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        size_policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        size_policy.setHeightForWidth(True)
        self.setSizePolicy(size_policy)

    def setPlainText(self, text):
        self.setText(text)

    def toPlainText(self):
        return self.text()


class UpdateCard(QWidget):
    """Version picker and release-note viewer backed by Git or PyAppify."""

    update_available_changed = Signal(bool)
    check_started = Signal()
    _versions_loaded = Signal(object)
    _update_finished = Signal(object)
    _git_versions_loaded = Signal(object)
    _git_update_finished = Signal(object)
    VERSION_COMBO_MIN_WIDTH = 100
    VERSION_COMBO_MAX_WIDTH = 240

    def __init__(self, current_version, pyappify_module, parent=None, exit_event=None, download_url=None):
        super().__init__(parent)
        self.current_version = current_version or getattr(pyappify_module, "app_version", None) or ""
        if "PYAPPIFY_PYTHON_TEST" in os.environ and not _is_numeric_version(self.current_version):
            logger.info(f"using v0.0.0 for nonnumeric test version {self.current_version!r}")
            self.current_version = "v0.0.0"
        self.pyappify_module = pyappify_module
        self.exit_event = exit_event
        self.download_url = download_url
        self.versions = []
        self._busy = False
        self.target_git_commit = None
        logger.info(
            f"initialized current_version={self.current_version!r}, "
            f"pyappify_module={getattr(pyappify_module, '__file__', type(pyappify_module).__name__)!r}, "
            f"pyappify_app_version={getattr(pyappify_module, 'app_version', None)!r}, "
            f"test_mode={'PYAPPIFY_PYTHON_TEST' in os.environ}"
        )

        self.version_combo = ComboBox(self)
        self.version_combo.setFixedWidth(self.VERSION_COMBO_MIN_WIDTH)
        self.version_combo.currentIndexChanged.connect(self._selection_changed)

        self.select_version_button = PushButton(FluentIcon.HISTORY, self.tr("Select Version"), self)
        self.select_version_button.clicked.connect(self._show_select_version_menu)
        self.select_version_button.setVisible(is_git_repository())

        self.check_button = PushButton(FluentIcon.SYNC, self.tr("Check for updates"), self)
        loading_icon_pixmap = QPixmap(16, 16)
        loading_icon_pixmap.fill(Qt.GlobalColor.transparent)
        self._loading_placeholder_icon = QIcon(loading_icon_pixmap)
        self.check_progress = IndeterminateProgressRing(self.check_button, start=False)
        self.check_progress.setFixedSize(16, 16)
        self.check_progress.setStrokeWidth(2)
        self.check_progress.hide()
        self.check_button.setMinimumWidth(self.check_button.sizeHint().width())
        self.check_button.installEventFilter(self)
        self.check_button.clicked.connect(self.check_for_updates)
        self.update_button = PrimaryPushButton(FluentIcon.UPDATE, self.tr("Update"), self)
        self.update_button.clicked.connect(self.update_to_selected_version)
        self.update_button.setEnabled(False)
        self.download_button = PrimaryPushButton(self.tr("Download"), self, icon=FluentIcon.DOWNLOAD)
        self.download_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.download_url)))
        self.download_button.hide()

        self.controls_layout = QHBoxLayout()
        self.controls_layout.setContentsMargins(0, 0, 11, 0)
        self.controls_layout.setSpacing(6)
        self.version_label = BodyLabel(self.tr("Version"), self)
        self.status_label = BodyLabel(self.tr("Click to check for updates"), self)
        self.status_label.setWordWrap(False)
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        status_size_policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.status_label.setSizePolicy(status_size_policy)
        self.controls_layout.addWidget(self.version_label)
        self.controls_layout.addWidget(self.version_combo)
        self.controls_layout.addWidget(self.status_label)
        self.controls_layout.addStretch(1)
        self.controls_layout.addWidget(self.download_button)
        self.controls_layout.addWidget(self.select_version_button)
        self.controls_layout.addWidget(self.check_button)
        self.controls_layout.addWidget(self.update_button)
        self._set_version_controls_visible(False)

        self.notes_edit = ChangeLogView("", self)
        self.notes_edit.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addLayout(self.controls_layout)
        layout.addWidget(self.notes_edit)

        self._versions_loaded.connect(self._apply_versions)
        self._update_finished.connect(self._apply_update_result)
        self._git_versions_loaded.connect(self._apply_git_check_result)
        self._git_update_finished.connect(self._apply_git_update_result)

    def check_for_updates(self):
        if self._busy:
            return
        if is_git_repository():
            self._set_busy(True, checking=True)
            self.check_started.emit()
            self._set_status(self.tr("Checking for updates…"))
            self._run_in_background(
                check_git_updates,
                self._git_versions_loaded,
                "git_updater.check_git_updates",
            )
            return

        get_versions = getattr(self.pyappify_module, "get_version_list", None)
        if not callable(get_versions):
            self._show_error(self.tr("Update checking is not supported."))
            return
        self._set_busy(True, checking=True)
        self.check_started.emit()
        self._set_status(self.tr("Checking for updates…"))
        self._run_in_background(
            lambda: get_versions(release_only=True, exit_event=self.exit_event),
            self._versions_loaded,
            "pyappify.get_version_list",
        )

    def _apply_git_check_result(self, result):
        self._set_busy(False, refresh_selection=False)
        successful, value = result
        if not successful:
            self._show_error(self.tr("Failed to check for updates: {error}").format(error=value))
            self.update_available_changed.emit(False)
            return

        has_update, notes, info = value
        self._set_version_controls_visible(False)
        if not has_update:
            self._set_notes("")
            self._set_status(self.tr("No updates available."))
            self.update_button.setEnabled(False)
            self.update_button.setText(self.tr("Current version"))
            self.update_available_changed.emit(False)
            return

        notes_text = "\n".join(f"• {n}" for n in notes) if notes else self.tr("New updates available from upstream.")
        self._set_notes(notes_text)
        self._set_status(self.tr("Update available"))
        self.update_button.setEnabled(True)
        self.update_button.setText(self.tr("Update"))
        self.update_available_changed.emit(True)

    def _show_select_version_menu(self):
        commits = get_local_commits()
        if not commits:
            self._set_status(self.tr("No local versions found."))
            return

        menu = RoundMenu(parent=self)
        current_text = self.tr("Current")
        for item in commits:
            short_h = item["short_hash"]
            msg = item["message"]
            is_head = item["is_head"]
            label = f"{short_h} - {msg}"
            if is_head:
                label += f" ({current_text})"
            action = Action(label, parent=menu)
            action.triggered.connect(lambda checked=False, c=item: self._on_version_selected(c))
            menu.addAction(action)

        summary_lines = [self.tr("Local pulled versions:")]
        for item in commits:
            mark = f" ({current_text})" if item["is_head"] else ""
            summary_lines.append(f"• {item['short_hash']} {item['message']}{mark}")
        self._set_notes("\n".join(summary_lines))

        pos = self.select_version_button.mapToGlobal(QPoint(0, self.select_version_button.height()))
        menu.exec(pos)

    def _on_version_selected(self, commit_item):
        self.target_git_commit = commit_item["hash"]
        short_h = commit_item["short_hash"]
        msg = commit_item["message"]
        is_head = commit_item["is_head"]

        if is_head:
            self._set_status(self.tr("Current version ({commit})").format(commit=short_h))
            self.update_button.setEnabled(False)
            self.update_button.setText(self.tr("Current version"))
        else:
            self._set_status(self.tr("Selected: {commit}").format(commit=short_h))
            self.update_button.setEnabled(True)
            self.update_button.setText(self.tr("Switch"))

        target_label = self.tr("Target version:")
        self._set_notes(f"{target_label}\n• {short_h} {msg}")

    def update_to_selected_version(self):
        if self._busy:
            return
        if is_git_repository():
            self._set_busy(True)
            target = self.target_git_commit
            action_desc = f"git_updater.pull_git_updates(target_commit={target!r})"
            self._set_status(self.tr("Switching version…") if target else self.tr("Updating repository…"))
            self._run_in_background(
                lambda: pull_git_updates(target_commit=target),
                self._git_update_finished,
                action_desc,
            )
            return

        if self.version_combo.currentIndex() < 0:
            return
        update_to_version = getattr(self.pyappify_module, "update_to_version", None)
        if not callable(update_to_version):
            self._show_error(self.tr("Updating is not supported by this PyAppify version."))
            return
        version = self.version_combo.currentText()
        self._set_busy(True)
        self._set_status(self.tr("Starting change to {version}…").format(version=version))
        self._run_in_background(
            lambda: update_to_version(version, exit_event=self.exit_event),
            self._update_finished,
            f"pyappify.update_to_version({version!r})",
        )

    def _apply_git_update_result(self, result):
        self._set_busy(False)
        successful, value = result
        if not successful:
            self._show_error(self.tr("Failed to change version: {error}").format(error=value))
            return

        self._set_status(self.tr("Update request accepted. The app will restart to apply it."))
        QTimer.singleShot(800, restart_with_uv)

    def _run_in_background(self, operation, signal, operation_name):
        def run():
            logger.info(f"calling {operation_name}")
            try:
                result = operation()
                logger.info(f"{operation_name} result={result!r}")
                signal.emit((True, result))
            except Exception as error:
                logger.error(f"{operation_name} failed: {error}", error)
                signal.emit((False, str(error)))

        threading.Thread(target=run, daemon=True, name="pyappify-update").start()

    def _apply_versions(self, result):
        self._set_busy(False, refresh_selection=False)
        successful, value = result
        if not successful:
            self.versions = []
            self.version_combo.clear()
            self._set_version_controls_visible(False)
            self.update_available_changed.emit(False)
            self._show_error(self.tr("Failed to check for updates: {error}").format(error=value))
            return

        self.versions = [item for item in value if isinstance(item, dict) and item.get("version")]
        self.version_combo.blockSignals(True)
        self.version_combo.clear()
        self.version_combo.addItems([str(item["version"]) for item in self.versions])
        self.version_combo.blockSignals(False)
        self._resize_version_combo()
        logger.info(
            f"loaded {len(self.versions)} valid versions into selector: "
            f"{[item['version'] for item in self.versions]!r}"
        )

        newest_update = next(
            (index for index, item in enumerate(self.versions)
             if self._compare_versions(str(item["version"]), self.current_version) > 0),
            None,
        )
        self.update_available_changed.emit(newest_update is not None)
        logger.info(
            f"update_available={newest_update is not None}, current_version={self.current_version!r}, "
            f"newest_update_index={newest_update!r}"
        )
        if not self.versions:
            self._set_version_controls_visible(False)
            self._set_notes("")
            self._set_status(self.tr("No versions are available."))
            self.update_button.setEnabled(False)
            return
        self._set_version_controls_visible(True)
        self._set_status("" if newest_update is not None else self.tr("No updates available."))
        self.version_combo.setCurrentIndex(0)
        self._selection_changed()

    def _selection_changed(self, _index=None):
        index = self.version_combo.currentIndex()
        if index < 0 or index >= len(self.versions):
            self.update_button.setEnabled(False)
            return
        selected = self.versions[index]
        target = str(selected["version"])
        direction = self._compare_versions(target, self.current_version)
        logger.debug(
            f"selected version={target!r}, current_version={self.current_version!r}, direction={direction}"
        )
        self.update_button.setEnabled(direction != 0 and not self._busy)
        self.update_button.setText(self.tr("Update") if direction > 0 else self.tr("Downgrade"))

        if direction == 0:
            self.update_button.setText(self.tr("Current version"))

        calculate_notes = getattr(self.pyappify_module, "calculate_update_notes", None)
        if not callable(calculate_notes):
            self._set_notes("")
            self._set_status(self.tr("Update-note calculation is not supported."), error=True)
            return
        try:
            notes = calculate_notes(self.versions, self.current_version, target)
            self._set_notes(
                "\n".join(f"• {note}" for note in notes) or self.tr("No release notes.")
            )
        except Exception as error:
            logger.error(f"pyappify.calculate_update_notes failed: {error}", error)
            self._set_notes("")
            self._set_status(self.tr("Failed to calculate update notes: {error}").format(error=error), error=True)

    def _resize_version_combo(self):
        font_metrics = QFontMetrics(self.version_combo.font())
        text_width = max(
            (font_metrics.horizontalAdvance(str(item["version"])) for item in self.versions),
            default=0,
        )
        content_width = text_width + 48
        width = max(self.VERSION_COMBO_MIN_WIDTH, min(self.VERSION_COMBO_MAX_WIDTH, content_width))
        self.version_combo.setFixedWidth(width)

    def _set_version_controls_visible(self, visible):
        self.version_label.setVisible(visible)
        self.version_combo.setVisible(visible)

    def _set_notes(self, text):
        self.notes_edit.setPlainText(text)
        self.notes_edit.setVisible(bool(text))

    def _set_check_loading(self, loading):
        if loading:
            self.check_button.setIcon(self._loading_placeholder_icon)
            self.check_progress.show()
            self.check_progress.start()
        else:
            self.check_progress.stop()
            self.check_progress.hide()
            self.check_button.setIcon(FluentIcon.SYNC)
        self._position_check_progress()

    def _position_check_progress(self):
        minimum_width = self.check_button.minimumSizeHint().width()
        x = 12 + max(0, (self.check_button.width() - minimum_width) // 2)
        self.check_progress.move(x, (self.check_button.height() - self.check_progress.height()) // 2)

    def eventFilter(self, watched, event):
        if watched is self.check_button and event.type() == QEvent.Type.Resize:
            self._position_check_progress()
        return super().eventFilter(watched, event)

    def _apply_update_result(self, result):
        self._set_busy(False)
        successful, value = result
        if successful:
            self._set_status(self.tr("Update request accepted. The app will restart to apply it."))
        else:
            self._show_error(self.tr("Failed to change version: {error}").format(error=value))

    def _set_busy(self, busy, checking=False, refresh_selection=True):
        self._busy = busy
        self.check_button.setEnabled(not busy)
        self.select_version_button.setEnabled(not busy)
        self._set_check_loading(busy and checking)
        self.version_combo.setEnabled(not busy)
        if busy:
            self.update_button.setEnabled(False)
        elif refresh_selection:
            self._selection_changed()

    def _show_error(self, message):
        self._set_busy(False, refresh_selection=False)
        self._set_notes("")
        self._set_status(message, error=True)

    def _set_status(self, message, error=False):
        self.status_label.setText(message)
        self.status_label.setToolTip(message if error else "")
        self.status_label.setStyleSheet("color: #d13438;" if error else "")
        self.download_button.setVisible(error and bool(self.download_url))

    def _compare_versions(self, left, right):
        if left == right:
            return 0
        is_greater = getattr(self.pyappify_module, "is_greater_version", None)
        if callable(is_greater):
            if is_greater(left, right):
                return 1
            if is_greater(right, left):
                return -1
        return 0
