import unittest
from unittest.mock import MagicMock, patch

from ok.device.interaction_methods.keys import (
    VK_OEM_1, VK_OEM_2, VK_OEM_3, VK_OEM_4, VK_OEM_5, VK_OEM_6, VK_OEM_7,
    VK_OEM_PLUS, VK_OEM_MINUS, VK_OEM_COMMA, VK_OEM_PERIOD,
    VK_NUMPAD0, VK_NUMPAD5, VK_NUMPAD9, VK_ADD, VK_SUBTRACT, VK_MULTIPLY, VK_DIVIDE,
    VK_LSHIFT, VK_RSHIFT, VK_LCONTROL, VK_RCONTROL, VK_LMENU, VK_RMENU,
    VK_LEFT, VK_RIGHT, VK_UP, VK_DOWN
)
from ok.device.interaction_methods.linux_proton_post_message import (
    LinuxProtonPostMessageInteraction,
    SCAN_CODE_MAP,
    EXTENDED_KEYS,
    make_lparam,
    make_mouse_lparam,
    WM_KEYDOWN,
    WM_KEYUP,
    WM_XBUTTONDOWN,
    WM_XBUTTONUP,
    XBUTTON1,
    XBUTTON2,
    MK_XBUTTON1,
    MK_XBUTTON2,
)


class TestProtonPostMessage(unittest.TestCase):

    def setUp(self):
        self.mock_capture = MagicMock(width=1920, height=1080)
        with patch("ok.device.interaction_methods.linux_proton_post_message.WineAgentClient") as mock_agent_cls:
            self.mock_agent = MagicMock()
            mock_agent_cls.return_value = self.mock_agent
            self.interaction = LinuxProtonPostMessageInteraction(self.mock_capture)
            self.interaction.agent = self.mock_agent

    def test_oem_symbols_key_codes(self):
        oem_cases = [
            ("`", VK_OEM_3), ("~", VK_OEM_3), ("tilde", VK_OEM_3),
            ("-", VK_OEM_MINUS), ("minus", VK_OEM_MINUS),
            ("=", VK_OEM_PLUS), ("equals", VK_OEM_PLUS),
            ("[", VK_OEM_4), ("]", VK_OEM_6),
            ("\\", VK_OEM_5), (";", VK_OEM_1),
            ("'", VK_OEM_7), (",", VK_OEM_COMMA),
            (".", VK_OEM_PERIOD), ("/", VK_OEM_2),
        ]
        for key_str, expected_vk in oem_cases:
            vk = self.interaction.get_key_code(key_str)
            self.assertEqual(expected_vk, vk, f"Failed for {key_str}")
            # Ensure scan code exists and is non-zero
            self.assertIn(vk, SCAN_CODE_MAP)
            self.assertGreater(SCAN_CODE_MAP[vk], 0)

    def test_numpad_key_codes(self):
        numpad_cases = [
            ("numpad0", VK_NUMPAD0), ("num0", VK_NUMPAD0),
            ("numpad5", VK_NUMPAD5), ("num5", VK_NUMPAD5),
            ("numpad9", VK_NUMPAD9), ("num9", VK_NUMPAD9),
            ("numpad_add", VK_ADD), ("numpad_sub", VK_SUBTRACT),
            ("numpad_mul", VK_MULTIPLY), ("numpad_div", VK_DIVIDE),
        ]
        for key_str, expected_vk in numpad_cases:
            vk = self.interaction.get_key_code(key_str)
            self.assertEqual(expected_vk, vk, f"Failed for numpad {key_str}")
            self.assertIn(vk, SCAN_CODE_MAP)
            self.assertGreater(SCAN_CODE_MAP[vk], 0)

    def test_modifiers_scan_codes(self):
        modifiers = [
            ("lshift", VK_LSHIFT, 0x2A),
            ("rshift", VK_RSHIFT, 0x36),
            ("lctrl", VK_LCONTROL, 0x1D),
            ("rctrl", VK_RCONTROL, 0x1D),
            ("lalt", VK_LMENU, 0x38),
            ("ralt", VK_RMENU, 0x38),
        ]
        for name, vk, expected_scan in modifiers:
            actual_vk = self.interaction.get_key_code(name)
            self.assertEqual(vk, actual_vk)
            self.assertEqual(expected_scan, SCAN_CODE_MAP.get(actual_vk))

    def test_extended_keys_lparam_flag(self):
        extended_vks = [VK_LEFT, VK_RIGHT, VK_UP, VK_DOWN, VK_RCONTROL, VK_RMENU, VK_DIVIDE]
        for vk in extended_vks:
            self.assertIn(vk, EXTENDED_KEYS)
            lparam = make_lparam(vk, is_up=False)
            # Bit 24 must be set for extended keys
            self.assertTrue(bool(lparam & (1 << 24)), f"Bit 24 not set for VK 0x{vk:x}")

        # Normal key (e.g. 'A' 0x41) must not have bit 24 set
        normal_lparam = make_lparam(0x41, is_up=False)
        self.assertFalse(bool(normal_lparam & (1 << 24)))

    def test_send_key_trigger(self):
        self.interaction.send_key_down("`", activate=False)
        self.mock_agent.post_message.assert_called_with(
            WM_KEYDOWN, VK_OEM_3, make_lparam(VK_OEM_3, is_up=False)
        )

        self.interaction.send_key_up("`")
        self.mock_agent.post_message.assert_called_with(
            WM_KEYUP, VK_OEM_3, make_lparam(VK_OEM_3, is_up=True)
        )

    def test_mouse_xbutton_side_keys_trigger(self):
        # Click Mouse 4 (XBUTTON1)
        self.interaction.click(500, 300, key="x1", move=False)
        expected_lparam = make_mouse_lparam(500, 300)
        expected_down_wparam = (XBUTTON1 << 16) | MK_XBUTTON1
        expected_up_wparam = (XBUTTON1 << 16)

        self.mock_agent.post_message.assert_any_call(
            WM_XBUTTONDOWN, expected_down_wparam, expected_lparam
        )
        self.mock_agent.post_message.assert_any_call(
            WM_XBUTTONUP, expected_up_wparam, expected_lparam
        )

        # Click Mouse 5 (XBUTTON2)
        self.interaction.click(600, 400, key="mouse5", move=False)
        expected_lparam2 = make_mouse_lparam(600, 400)
        expected_down_wparam2 = (XBUTTON2 << 16) | MK_XBUTTON2
        expected_up_wparam2 = (XBUTTON2 << 16)

        self.mock_agent.post_message.assert_any_call(
            WM_XBUTTONDOWN, expected_down_wparam2, expected_lparam2
        )
        self.mock_agent.post_message.assert_any_call(
            WM_XBUTTONUP, expected_up_wparam2, expected_lparam2
        )


if __name__ == "__main__":
    unittest.main()
