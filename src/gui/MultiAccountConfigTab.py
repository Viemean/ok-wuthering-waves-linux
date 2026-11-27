from copy import deepcopy
from datetime import datetime
import json
import time

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QLineEdit, QSizePolicy,
    QStyleOptionViewItem, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ok import og
from ok.core.icons import Icon
from ok.ui.qt.kit.buttons import Button
from ok.ui.qt.kit.cards import Card
from ok.ui.qt.kit.feedback import show_toast
from ok.ui.qt.kit.inputs import ComboBox
from ok.ui.qt.kit.labels import Label
from ok.ui.qt.kit.switch import Switch
from ok.ui.qt.kit.table import Table
from ok.ui.qt.shell.run_bar import format_elapsed
from ok.ui.qt.tasks.config_editors import config_editor
from ok.ui.qt.tasks.config_form import ConfigContentMixin
from ok.ui.qt.widget.CustomTab import CustomTab
from ok.ui.qt.widget.UpdateConfigWidgetItem import value_to_string
from src.task.MultiAccountConfigTask import MultiAccountConfigTask
from src.task.account.MultiAccountConfigStore import (
    MultiAccountConfigStore, collect_available_tasks, display_account, task_reference,
)
from src.task.account.RuntimeTaskConfig import effective_config


class AccountStatusTable(Table):
    """Show complete wrapped rows; let the page own vertical scrolling."""

    def __init__(self):
        super().__init__()
        self.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.size_timer = QTimer(self)
        self.size_timer.setSingleShot(True)
        self.size_timer.timeout.connect(self.fit_contents)

    def schedule_fit(self):
        self.size_timer.start(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if event.size().width() != event.oldSize().width():
            self.schedule_fit()

    def fit_contents(self):
        width = self.viewport().width()
        self.setColumnWidth(0, int(width * 0.3))
        self.setColumnWidth(1, width - self.columnWidth(0))
        for row in range(self.rowCount()):
            row_height = self.verticalHeader().defaultSectionSize()
            for column in range(self.columnCount()):
                item = self.item(row, column)
                if item is None:
                    continue
                option = QStyleOptionViewItem()
                self.itemDelegate().initStyleOption(option, self.indexFromItem(item))
                bounds = QFontMetrics(option.font).boundingRect(
                    0, 0, max(1, self.columnWidth(column) - 24), 100000,
                    Qt.TextWordWrap, item.text())
                row_height = max(row_height, bounds.height() + 20)
            self.setRowHeight(row, row_height)
        height = self.horizontalHeader().height() + self.verticalHeader().length() + 2 * self.frameWidth()
        self.setFixedHeight(height)
        self.updateGeometry()


class AccountConfigContent(ConfigContentMixin, QWidget):
    """Use exactly the task page's widget factory and sub-config visibility rules."""

    def __init__(self, task, config, owner):
        super().__init__(owner)
        self.owner = owner
        self.viewLayout = QVBoxLayout(self)
        self._init_config_content(task, config, task.default_config,
                                  task.config_description, task.config_type)

    def _create_config_widget(self, key, value):
        return config_editor(self.config_type, self.config_description, self.config, key, value, self.task)

    def _mark_sub_config(self, widget):
        widget.set_indent(True)

    def _adjust_config_content_size(self):
        self.viewLayout.invalidate()
        self.updateGeometry()
        self.owner.schedule_resize()


def _form_row(title: str, description: str | None, control: QWidget) -> QWidget:
    row = QWidget()
    text = QVBoxLayout()
    text.setContentsMargins(0, 0, 0, 0)
    text.setSpacing(2)
    text.addWidget(Label(title, 'strong', row))
    if description:
        text.addWidget(Label(description, 'secondary', row, word_wrap=True))
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 4, 0, 4)
    layout.setSpacing(16)
    layout.addLayout(text, 1)
    layout.addWidget(control)
    return row


class AccountTaskCard(Card):
    def __init__(self, account, tasks, remove, parent=None):
        super().__init__(parent, look='inset')
        self.tasks = tasks
        self.reference = deepcopy(account.get('task'))
        self.values = deepcopy(account.get('config', {}))
        self.content = None
        self.drafts = {}
        self.isExpand = False
        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.resize_content)

        self.card = QWidget(self)
        self.title_label = Label('新账号', 'strong', self.card)
        self.content_label = Label('无', 'secondary', self.card)
        title_box = QVBoxLayout()
        title_box.setContentsMargins(0, 0, 0, 0)
        title_box.setSpacing(2)
        title_box.addWidget(self.title_label)
        title_box.addWidget(self.content_label)

        self.result_label = Label('未运行', 'secondary', self.card)
        self.enabled_switch = Switch(parent=self.card)
        self.enabled_switch.setChecked(account.get('enabled', True))
        self.expand_button = Button(icon='chevron-down', variant='subtle', size='small', parent=self.card)
        self.expand_button.clicked.connect(lambda: self.setExpand(not self.isExpand))

        header_layout = QHBoxLayout(self.card)
        header_layout.setContentsMargins(16, 12, 12, 12)
        header_layout.setSpacing(12)
        header_layout.addLayout(title_box, 1)
        header_layout.addWidget(self.result_label)
        header_layout.addWidget(self.enabled_switch)
        header_layout.addWidget(self.expand_button)

        self.body = QWidget(self)
        self.viewLayout = QVBoxLayout(self.body)
        self.viewLayout.setContentsMargins(16, 4, 16, 14)
        self.viewLayout.setSpacing(8)

        self.account_edit = QLineEdit()
        self.account_edit.setPlaceholderText('去掉所有 *，例如 1231234 或 Ab12@outlook.com')
        self.account_edit.setMinimumWidth(280)
        self.account_edit.setText(account.get('account_key', ''))
        self.viewLayout.addWidget(_form_row('账号标识', None, self.account_edit))

        self.task_combo = ComboBox()
        self.task_combo.setMinimumWidth(280)
        self.task_combo.addItem('无', userData=None)
        selected_index = 0
        for task in tasks:
            reference = task_reference(task)
            self.task_combo.addItem(og.app.tr(task.name), userData=reference)
            if reference == self.reference:
                selected_index = self.task_combo.count() - 1
        if self.reference is not None and selected_index == 0:
            self.task_combo.setPlaceholderText(f"任务不可用：{self.reference['class']}，请重新选择")
            selected_index = -1
        self.task_combo.setCurrentIndex(selected_index)
        self.viewLayout.addWidget(_form_row('执行任务', '选择一次性任务；“无”仅测试切号。', self.task_combo))

        self.config_container = QWidget()
        self.config_layout = QVBoxLayout(self.config_container)
        self.config_layout.setContentsMargins(0, 0, 0, 0)
        self.viewLayout.addWidget(self.config_container)
        self.delete_button = Button('删除账号', 'trash')
        self.delete_button.clicked.connect(lambda: remove(self))
        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(self.delete_button)
        self.viewLayout.addLayout(footer)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self.card)
        root.addWidget(self.body)
        self.body.hide()
        self.card.setFixedHeight(self.card.sizeHint().height())

        self.account_edit.textChanged.connect(self.update_header)
        self.task_combo.currentIndexChanged.connect(self.task_changed)
        self.render_config()
        self.update_header()
        self.resize_content()

    def setExpand(self, expand: bool):
        self.isExpand = bool(expand)
        self.body.setVisible(self.isExpand)
        self.expand_button.set_icon('chevron-up' if self.isExpand else 'chevron-down')
        self.resize_content()

    def selected_task(self):
        return next((task for task in self.tasks if task_reference(task) == self.reference), None)

    def render_config(self):
        if self.content is not None:
            self.config_layout.removeWidget(self.content)
            self.content.hide()
            self.content.deleteLater()
            self.content = None
        task = self.selected_task()
        if task is not None:
            self.values = effective_config(task, self.values)
            self.content = AccountConfigContent(task, self.values, self)
            self.config_layout.addWidget(self.content)
        self.schedule_resize()

    def schedule_resize(self):
        self.resize_timer.start(0)

    def resize_content(self):
        if self.content is not None:
            self.content.viewLayout.invalidate()
            self.content.viewLayout.activate()
            self.content.updateGeometry()
        self.config_layout.invalidate()
        self.config_layout.activate()
        self.config_container.updateGeometry()
        self.viewLayout.invalidate()
        self.viewLayout.activate()
        header_height = self.card.sizeHint().height()
        self.card.setFixedHeight(header_height)
        if self.isExpand:
            self.setFixedHeight(header_height + self.viewLayout.sizeHint().height())
        else:
            self.setFixedHeight(header_height)

    def update_result(self, result):
        if not result:
            self.result_label.setText('未运行')
            self.result_label.setToolTip('该账号尚无运行记录')
            return
        status = result.get('status')
        stamp = result.get('finished_at', '')
        try:
            stamp = datetime.fromisoformat(stamp).astimezone().strftime('%Y-%m-%d %H:%M:%S')
        except (TypeError, ValueError):
            stamp = '时间未知'
        symbol = '✓' if status == 'success' else '✗'
        label = {'success': '成功', 'failed': '失败', 'cancelled': '已停止'}.get(status, '未知')
        self.result_label.setText(f'{symbol} {stamp}')
        self.result_label.setToolTip(f'上次运行：{label}\n结束时间：{stamp}\n{result.get("message", "")}')

    @staticmethod
    def _draft_key(reference):
        return json.dumps(reference, sort_keys=True)

    def task_changed(self, index):
        # Retain unsaved edits when switching away and back within this card.
        self.drafts[self._draft_key(self.reference)] = deepcopy(dict(self.values))
        self.reference = self.task_combo.itemData(index)
        self.values = self.drafts.get(self._draft_key(self.reference), {})
        self.render_config()
        self.update_header()

    def update_header(self, *_):
        self.title_label.setText(display_account(self.account_edit.text()) or '新账号')
        self.content_label.setText(self.task_combo.currentText() or '任务不可用，请重新选择')

    def snapshot(self):
        return {'account_key': self.account_edit.text(), 'task': deepcopy(self.reference),
                'enabled': self.enabled_switch.isChecked(),
                'config': deepcopy(dict(self.values)) if self.reference else {}}


class MultiAccountConfigTab(CustomTab):
    def __init__(self):
        super().__init__()
        self.cards = []
        self.loaded = False
        self.store = None
        self.runner = None
        self.dismissed_run = None
        self.info_run = None
        self.elapsed_text = ''
        self.results_signature = None
        self.run_results = {}
        header = QHBoxLayout()
        header.addWidget(Label('多账号配置', 'subtitle'))
        header.addStretch(1)
        self.start_button = Button('开始执行', 'play', 'primary')
        self.stop_button = Button('停止执行', 'x')
        self.start_button.clicked.connect(self.start_clicked)
        self.stop_button.clicked.connect(self.stop_clicked)
        header.addWidget(self.start_button)
        header.addWidget(self.stop_button)
        self.addLayout(header)
        self.add_widget(Label('按卡片顺序执行。配置独立保存，任务失败时停止后续账号。', 'secondary'))
        self.account_hint = Label(
            '账号统一删除所有 * 后完整匹配，保留大小写。'
            '例如 Ab****12@outlook.com 填 Ab12@outlook.com；159****1234 填 1591234。',
            'secondary',
            word_wrap=True,
        )
        self.add_widget(self.account_hint)
        self.status_table = AccountStatusTable()
        self.status_table.setColumnCount(2)
        self.status_table.setHorizontalHeaderLabels([self.tr('Info'), self.tr('Value')])
        self.status_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.status_card = self.add_card('运行状态 / 日志', self.status_table)
        self.close_info_button = Button(icon='x', variant='subtle', size='small', parent=self.status_card)
        self.close_info_button.setToolTip(self.tr('Close'))
        self.close_info_button.clicked.connect(self.close_task_info)
        self.status_card.add_top_widget(self.close_info_button)
        self.status_card.hide()

        self.accounts_widget = QWidget()
        self.accounts_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.accounts_layout = QVBoxLayout(self.accounts_widget)
        self.accounts_layout.setContentsMargins(0, 0, 0, 0)
        self.accounts_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.accounts_layout.setSpacing(6)
        self.add_widget(self.accounts_widget)
        footer = QHBoxLayout()
        self.add_button = Button('新增账号', 'plus')
        self.save_button = Button('保存配置', 'check', 'primary')
        self.add_button.clicked.connect(lambda: self.add_account())
        self.save_button.clicked.connect(lambda: self.save_accounts())
        footer.addWidget(self.add_button)
        footer.addStretch(1)
        footer.addWidget(self.save_button)
        self.addLayout(footer)
        self.vBoxLayout.addStretch(1)
        self.timer = QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.refresh_status)
        self.refresh_status()

    @property
    def name(self):
        return '多账号配置'

    @property
    def icon(self):
        return Icon.PEOPLE

    def showEvent(self, event):
        super().showEvent(event)
        # MainWindow injects executor only after CustomTab construction.
        if not self.loaded and self.executor is not None:
            self.store = MultiAccountConfigStore(self.executor.config_folder)
            self.runner = self.executor.get_task_by_class(MultiAccountConfigTask)
            try:
                accounts = self.store.load()
            except (OSError, ValueError) as error:
                self.show_error(error)
            else:
                for account in accounts:
                    self.add_account(account)
                self.loaded = True
        self.refresh_status()
        self.timer.start()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def add_account(self, account=None):
        account = account or {'account_key': '', 'task': None, 'config': {}}
        card = AccountTaskCard(account, collect_available_tasks(self.executor), self.remove_account)
        card.account_edit.textChanged.connect(lambda: self.update_card_result(card))
        self.cards.append(card)
        self.update_card_result(card)
        self.accounts_layout.addWidget(card)
        if not account['account_key']:
            card.setExpand(True)

    def remove_account(self, card):
        self.cards.remove(card)
        self.accounts_layout.removeWidget(card)
        card.hide()
        card.deleteLater()

    def show_error(self, error):
        show_toast(self.window(), str(error), self.tr('Multi-account configuration'), tone='danger', duration=6000)

    def save_accounts(self, notify=True):
        if not self.loaded or (self.runner and self.runner.enabled):
            return False
        try:
            self.store.save([card.snapshot() for card in self.cards], self.executor)
        except (OSError, ValueError, TypeError) as error:
            self.show_error(error)
            return False
        if notify:
            show_toast(self.window(), self.tr('Configuration saved'), self.tr('Multi-account configuration'),
                       tone='success', duration=2000)
        return True

    def start_clicked(self):
        if not self.runner or self.runner.enabled:
            return
        if not any(card.enabled_switch.isChecked() for card in self.cards):
            self.show_error('请先新增并启用至少一个账号。')
            return
        if self.save_accounts(notify=False):
            og.app.start_controller.start(self.runner)
            self.refresh_status()

    def stop_clicked(self):
        if self.runner and self.runner.enabled:
            self.runner.disable()
            self.runner.unpause()

    def refresh_status(self):
        self.refresh_results()
        busy = bool(self.runner and self.runner.enabled)
        ready = self.loaded and self.runner is not None
        self.start_button.setEnabled(ready and not busy)
        self.stop_button.setEnabled(busy)
        for widget in (self.accounts_widget, self.add_button, self.save_button):
            widget.setEnabled(ready and not busy)
        start_time = self.runner.start_time if self.runner else 0
        if not start_time or self.dismissed_run == start_time:
            self.status_card.hide()
            return
        if self.info_run != start_time:
            self.info_run = start_time
            self.elapsed_text = format_elapsed(time.time() - start_time)
        if busy:
            self.elapsed_text = format_elapsed(time.time() - start_time)
        status = self.tr('Running') if busy else self.tr('Completed')
        self.status_card.titleLabel.setText(
            f'{status}: {self.tr(self.runner.name)} {self.tr("Time Elapsed")}: {self.elapsed_text}')
        self.status_card.show()
        info = dict(self.runner.info) if self.runner else {}
        self.status_table.setRowCount(len(info))
        for row, (key, value) in enumerate(info.items()):
            text = value_to_string(value)
            if self.status_table.item(row, 0) is None:
                self.status_table.setItem(row, 0, QTableWidgetItem())
                self.status_table.setItem(row, 1, QTableWidgetItem())
            self.status_table.item(row, 0).setText(og.app.tr(key))
            # gettext uses the empty msgid for catalog metadata, not an empty label.
            self.status_table.item(row, 1).setText(og.app.tr(text) if text else '')
        self.status_table.schedule_fit()

    def close_task_info(self):
        self.dismissed_run = self.info_run
        self.status_card.hide()

    def update_card_result(self, card):
        card.update_result(self.run_results.get(card.account_edit.text()))

    def refresh_results(self):
        if self.store is None:
            return
        signature = None
        try:
            signature = self.store.results_path.stat().st_mtime_ns if self.store.results_path.exists() else 0
            if signature == self.results_signature:
                return
            self.run_results = self.store.load_results()
        except (OSError, ValueError) as error:
            self.show_error(error)
            # Retry when the file changes rather than showing an error every tick.
            self.results_signature = signature
            return
        self.results_signature = signature
        for card in self.cards:
            self.update_card_result(card)
