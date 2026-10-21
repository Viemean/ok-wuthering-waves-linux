import time
from PySide6.QtCore import Qt, Signal, QCoreApplication
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QWidget, QFileDialog, QCompleter, QVBoxLayout, QHBoxLayout
from qfluentwidgets import PushButton, FlowLayout, ComboBox, SearchLineEdit, TextEdit

from ok import Config, og
from ok import Handler
from ok import Logger
from ok.util.dump import dump_threads
from ok.device.capture import ImageCaptureMethod
from ok.device.interaction import DoNothingInteraction
from ok.ui.qt.i18n.GettextTranslator import convert_to_mo_files
from ok.ui.qt.util.Alert import alert_info, alert_error
from ok.ui.qt.widget.Tab import Tab
from ok.util.explorer import open_explorer_folder, reveal_in_explorer

logger = Logger.get_logger(__name__)


class DebugTab(Tab):
    update_result_text: Signal = Signal(str)

    def __init__(self, app_config, exit_event):

        super().__init__()
        self.config = Config('debug', {'target_task': "", 'target_images': [], 'target_function': ""}
                             )
        tool_widget = QWidget()
        layout = FlowLayout(tool_widget, False)

        layout.setContentsMargins(0, 0, 0, 0)
        layout.setVerticalSpacing(20)
        layout.setHorizontalSpacing(10)
        self.handler = Handler(exit_event, "DebugTab")

        self.add_card(self.tr("Debug Tool"), tool_widget)

        dump_button = PushButton(self.tr("Dump Threads(HotKey:Ctrl+Alt+D)"))
        dump_button.clicked.connect(lambda: self.handler.post(dump_threads))
        layout.addWidget(dump_button)
        self.dump_shortcut = QShortcut(QKeySequence("Ctrl+Alt+D"), self)
        self.dump_shortcut.activated.connect(lambda: self.handler.post(dump_threads))

        capture_button = PushButton(self.tr("Capture Screenshot"))
        capture_button.clicked.connect(lambda: self.handler.post(capture))
        layout.addWidget(capture_button)

        ocr_button = PushButton("OCR")
        ocr_button.clicked.connect(lambda: self.handler.post(self.ocr_log))
        layout.addWidget(ocr_button)

        gen_tr_button = PushButton(self.tr("Generate i18n files"))
        gen_tr_button.clicked.connect(self.gen_tr)
        layout.addWidget(gen_tr_button)

        convert_tr_button = PushButton(self.tr("Convert i18n files"))
        convert_tr_button.clicked.connect(convert_to_mo_files)
        layout.addWidget(convert_tr_button)

        call_task_widget = QWidget()
        call_task_container = QVBoxLayout(call_task_widget)
        call_task_layout = QHBoxLayout()
        call_task_container.addLayout(call_task_layout)
        self.add_card(self.tr("Debug Task Function"), call_task_widget)
        images = self.config.get("target_images")
        self.select_screenshot_button = PushButton(
            self.tr('{num} images selected').format(num=len(images)) if images else self.tr("Select Screenshots"))
        self.select_screenshot_button.clicked.connect(self.select_screenshot)
        call_task_layout.addWidget(self.select_screenshot_button)

        self.tasks_combo_box = ComboBox()
        call_task_layout.addWidget(self.tasks_combo_box)
        tasks = og.executor.get_all_tasks()
        class_names = [obj.__class__.__name__ for obj in tasks]
        self.tasks_combo_box.addItems(class_names)
        self.tasks_combo_box.currentTextChanged.connect(self.task_changed)

        self.target_function_edit = SearchLineEdit(self)
        self.target_function_edit.setPlaceholderText(self.tr('Type a function or property'))
        self.target_function_edit.setClearButtonEnabled(True)
        if self.config.get('target_function'):
            self.target_function_edit.setText(self.config.get('target_function'))
        call_task_layout.addWidget(self.target_function_edit, stretch=1)

        if self.config.get('target_task') in class_names:
            self.tasks_combo_box.setText(self.config.get('target_task'))
            self.task_changed(self.config.get('target_task'))
        else:
            self.tasks_combo_box.setCurrentIndex(0)
            self.config['target_task'] = class_names[0]

        self.call_button = PushButton(self.tr("Call"))
        self.call_button.clicked.connect(lambda: self.handler.post(self.call))

        call_task_layout.addWidget(self.call_button)

        self.result_edit = TextEdit()
        call_task_container.addWidget(self.result_edit, stretch=1)
        self.update_result_text.connect(self.result_edit.setText)
        self.capture_shortcut = QShortcut(QKeySequence("Ctrl+Alt+S"), self)
        self.capture_shortcut.activated.connect(lambda: self.handler.post(capture))

    def gen_tr(self):
        folder = og.app.gen_tr_po_files()
        reveal_in_explorer(folder)

    def call(self):
        func_name = self.target_function_edit.text()
        task_name = self.config.get('target_task')
        task = og.executor.get_task_by_class_name(task_name)

        if not hasattr(task, func_name):
            alert_error(self.tr(f"No such attr: {func_name}"))
            return
        old_capture = og.device_manager.capture_method
        old_interaction = og.device_manager.interaction
        try:
            images = self.config.get("target_images")
            if images:
                og.device_manager.capture_method = ImageCaptureMethod(og.device_manager.exit_event, images)
                og.device_manager.interaction = DoNothingInteraction(og.device_manager.capture_method)
            else:
                task.next_frame()
            og.executor.debug_mode = True
            attr = getattr(task, func_name)
            if callable(attr):
                result = str(attr())
            else:
                result = str(attr)
        except Exception as e:
            logger.error('debug call exception', e)
            result = Logger.exception_to_str(e)
        og.executor.debug_mode = False
        og.device_manager.capture_method = old_capture
        og.device_manager.interaction = old_interaction
        self.update_result_text.emit(result)
        self.config['target_function'] = func_name
        alert_info(self.tr(f"call success: {result}"))

    def ocr_log(self):
        try:
            result = og.executor.get_all_tasks()[0].ocr(log=True)
            self.update_result_text.emit(str(result))
            alert_info(self.tr(f"OCR success (Logged): {result}"))
            folder = og.ok.screenshot.screenshot_folder
            if folder:
                open_explorer_folder(folder)
        except Exception as e:
            logger.error('debug ocr_log exception', e)
            return

    def task_changed(self, text):
        self.config['target_task'] = text
        task = og.executor.get_task_by_class_name(text)
        functions = [func for func in dir(task)]
        completer = QCompleter(functions, self.target_function_edit)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setMaxVisibleItems(10)
        self.target_function_edit.setCompleter(completer)

    def select_screenshot(self):
        file_names, _ = QFileDialog.getOpenFileNames(None, "Open Image", "", "Image Files (*.png *.jpg *.bmp)")

        if file_names:
            logger.info(f"Selected files: {file_names}")
            self.select_screenshot_button.setText(self.tr('{num} images selected').format(num=len(file_names)))
            self.config['target_images'] = file_names
        else:
            self.select_screenshot_button.setText(self.tr("Drop or Select Screenshot"))
            self.config['target_images'] = None


def capture(processor=None):
    if og.device_manager.capture_method is not None:
        logger.info(f'og.device_manager.capture_method {og.device_manager.capture_method}')
        try:
            frame = og.device_manager.capture_method.get_frame()
            if frame is not None:
                current_capture = str(og.device_manager.capture_method) + '_' + str(time.time() * 1000)
                file_path = og.ok.screenshot.generate_screen_shot(frame, og.ok.screenshot.ui_dict,
                                                                  og.ok.screenshot.screenshot_folder,
                                                                  current_capture, True, None, processor=processor)

                reveal_in_explorer(file_path)
                logger.info(f'captured screenshot: {current_capture}')
                alert_info(QCoreApplication.translate('DebugTab', 'Capture Success'), True)
            else:
                alert_error(QCoreApplication.translate('DebugTab', 'Capture returned None'))
        except Exception as e:
            alert_error(QCoreApplication.translate('DebugTab', str(e)))
    else:
        alert_error(QCoreApplication.translate('DebugTab', 'No Capture Available or Selected'))
