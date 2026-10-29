import os
import unittest
from unittest.mock import Mock, call, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from ok.device.interaction_methods.keys import (
    is_mouse_button, get_mouse_button, XBUTTON1, XBUTTON2,
    MOUSE_XBUTTON1, MOUSE_XBUTTON2
)
from ok.device.interaction_methods.pynput import PynputInteraction
from ok.ui.qt.tasks.LabelAndLineEdit import LabelAndLineEdit, GlobalMouseButtonFilter
from ok.task.task import VALID_NAMED_KEYS, ExecutorOperation


class TestMouseButtons(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])

    def test_valid_named_keys_contains_mouse_buttons(self):
        for btn in ['mouse4', 'mouse5', 'xbutton1', 'xbutton2']:
            self.assertIn(btn, VALID_NAMED_KEYS)

    def test_executor_operation_validates_mouse_keys(self):
        op = ExecutorOperation(Mock(), Mock())
        self.assertEqual(op.validate_key('mouse4'), 'mouse4')
        self.assertEqual(op.validate_key('MOUSE5'), 'MOUSE5')
        self.assertEqual(op.validate_key('xbutton1'), 'xbutton1')

    def test_is_and_get_mouse_button(self):
        self.assertTrue(is_mouse_button('mouse4'))
        self.assertTrue(is_mouse_button('MOUSE5'))
        self.assertFalse(is_mouse_button('ctrl'))
        self.assertEqual(get_mouse_button('mouse4'), XBUTTON1)
        self.assertEqual(get_mouse_button('mouse5'), XBUTTON2)

    def test_global_mouse_button_filter_fills_hotkey(self):
        from ok import og
        orig_app = getattr(og, 'app', None)
        og.app = Mock(tr=lambda text: text)
        self.addCleanup(lambda: setattr(og, 'app', orig_app))

        config_desc = {'key': 'Test Key'}
        config = {'key': 't'}
        widget = LabelAndLineEdit(config_desc, config, 'key')
        widget.show()
        self.addCleanup(widget.close)

        line_edit = widget.line_edit
        line_edit.setFocus()
        QApplication.processEvents()
        self.assertEqual(QApplication.focusWidget(), line_edit)

        event_filter = GlobalMouseButtonFilter()
        press_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(10, 10),
            Qt.MouseButton.XButton1,
            Qt.MouseButton.XButton1,
            Qt.KeyboardModifier.NoModifier
        )

        consumed = event_filter.eventFilter(line_edit, press_event)
        self.assertTrue(consumed)
        self.assertEqual(line_edit.text(), 'mouse4')

        press_event_5 = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(10, 10),
            Qt.MouseButton.XButton2,
            Qt.MouseButton.XButton2,
            Qt.KeyboardModifier.NoModifier
        )
        consumed_5 = event_filter.eventFilter(line_edit, press_event_5)
        self.assertTrue(consumed_5)
        self.assertEqual(line_edit.text(), 'mouse5')


class TestSideButtonRegressions(unittest.TestCase):
    def test_pynput_side_button_press_release_and_aliases(self):
        from pynput import mouse
        btn_x1 = getattr(mouse.Button, 'x1', getattr(mouse.Button, 'button8', mouse.Button.unknown))
        btn_x2 = getattr(mouse.Button, 'x2', getattr(mouse.Button, 'button9', mouse.Button.unknown))
        interaction = PynputInteraction.__new__(PynputInteraction)
        interaction.check_clickable = False
        for key, button in [('mouse4', btn_x1), ('xbutton1', btn_x1),
                            ('mouse5', btn_x2), ('XBUTTON2', btn_x2)]:
            with self.subTest(key=key), patch('pynput.mouse.Controller') as controller, \
                    patch('pynput.keyboard.Controller') as keyboard_controller, \
                    patch('ok.device.interaction_methods.pynput.time.sleep') as sleep:
                interaction.send_key(key, down_time=.03)
                self.assertEqual(controller.return_value.mock_calls,
                                 [call.press(button), call.release(button)])
                sleep.assert_called_once_with(.03)
                controller.return_value.reset_mock()
                interaction.send_key_down(key)
                interaction.send_key_up(key)
                self.assertEqual(controller.return_value.mock_calls,
                                 [call.press(button), call.release(button)])
                keyboard_controller.assert_not_called()

    def test_pynput_keyboard_dispatch_is_preserved(self):
        from pynput import keyboard
        interaction = PynputInteraction.__new__(PynputInteraction)
        interaction.check_clickable = False
        with patch('pynput.keyboard.Controller') as controller, \
                patch('pynput.mouse.Controller') as mouse_controller, \
                patch('ok.device.interaction_methods.pynput.time.sleep'):
            interaction.send_key('lctrl')
            interaction.send_key_down('a')
            interaction.send_key_up('a')
            self.assertEqual(controller.return_value.mock_calls,
                             [call.press(keyboard.Key.ctrl_l), call.release(keyboard.Key.ctrl_l),
                              call.press('a'), call.release('a')])
            mouse_controller.assert_not_called()

    def test_pynput_background_window_does_not_dispatch_side_buttons(self):
        interaction = PynputInteraction.__new__(PynputInteraction)
        interaction.check_clickable = True
        interaction.hwnd_window = Mock()
        interaction.hwnd_window.is_foreground.return_value = False
        with patch('pynput.mouse.Controller') as controller:
            interaction.send_key('mouse4')
            interaction.send_key_down('mouse4')
            interaction.send_key_up('mouse4')
            controller.assert_not_called()


if __name__ == '__main__':
    unittest.main()
