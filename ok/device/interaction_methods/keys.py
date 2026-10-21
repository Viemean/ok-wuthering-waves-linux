# Virtual key code constants for Wine agent IPC protocol
VK_BACK = 0x08
VK_TAB = 0x09
VK_RETURN = 0x0D
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_CAPITAL = 0x14
VK_ESCAPE = 0x1B
VK_SPACE = 0x20
VK_PRIOR = 0x21
VK_NEXT = 0x22
VK_END = 0x23
VK_HOME = 0x24
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28
VK_SNAPSHOT = 0x2C
VK_INSERT = 0x2D
VK_DELETE = 0x2E
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_F1 = 0x70
VK_F2 = 0x71
VK_F3 = 0x72
VK_F4 = 0x73
VK_F5 = 0x74
VK_F6 = 0x75
VK_F7 = 0x76
VK_F8 = 0x77
VK_F9 = 0x78
VK_F10 = 0x79
VK_F11 = 0x7A
VK_F12 = 0x7B
VK_NUMLOCK = 0x90
VK_SCROLL = 0x91
VK_LSHIFT = 0xA0
VK_RSHIFT = 0xA1
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_LMENU = 0xA4
VK_RMENU = 0xA5

PYDIRECT_KEY_MAP = {}


def normalize_pydirect_key(key):
    return str(key)


vk_key_dict = {
    'F1': VK_F1,
    'F2': VK_F2,
    'F3': VK_F3,
    'F4': VK_F4,
    'F5': VK_F5,
    'F6': VK_F6,
    'F7': VK_F7,
    'F8': VK_F8,
    'F9': VK_F9,
    'F10': VK_F10,
    'F11': VK_F11,
    'F12': VK_F12,
    'ESC': VK_ESCAPE,
    'CTRL': VK_CONTROL,
    'CONTROL': VK_CONTROL,
    'LCTRL': VK_LCONTROL,
    'RCTRL': VK_RCONTROL,
    'CTRL_L': VK_LCONTROL,
    'CTRL_R': VK_RCONTROL,
    'LCONTROL': VK_LCONTROL,
    'RCONTROL': VK_RCONTROL,
    'ALT': VK_MENU,
    'LALT': VK_LMENU,
    'RALT': VK_RMENU,
    'ALT_L': VK_LMENU,
    'ALT_R': VK_RMENU,
    'SHIFT': VK_SHIFT,
    'LSHIFT': VK_LSHIFT,
    'RSHIFT': VK_RSHIFT,
    'SHIFT_L': VK_LSHIFT,
    'SHIFT_R': VK_RSHIFT,
    'TAB': VK_TAB,
    'ENTER': VK_RETURN,
    'RETURN': VK_RETURN,
    'SPACE': VK_SPACE,
    'LEFT': VK_LEFT,
    'UP': VK_UP,
    'RIGHT': VK_RIGHT,
    'DOWN': VK_DOWN,
    'BACKSPACE': VK_BACK,
    'PAGEUP': VK_PRIOR,
    'PAGE_UP': VK_PRIOR,
    'PAGEDOWN': VK_NEXT,
    'PAGE_DOWN': VK_NEXT,
    'HOME': VK_HOME,
    'END': VK_END,
    'INSERT': VK_INSERT,
    'DELETE': VK_DELETE,
    'CAPSLOCK': VK_CAPITAL,
    'CAPS_LOCK': VK_CAPITAL,
    'NUMLOCK': VK_NUMLOCK,
    'NUM_LOCK': VK_NUMLOCK,
    'SCROLLLOCK': VK_SCROLL,
    'SCROLL_LOCK': VK_SCROLL,
    'PRINTSCREEN': VK_SNAPSHOT,
    'PRINT_SCREEN': VK_SNAPSHOT,
    'WIN': VK_LWIN,
    'WINDOWS': VK_LWIN,
    'COMMAND': VK_LWIN,
    'CMD': VK_LWIN,
    'CMD_L': VK_LWIN,
    'CMD_R': VK_RWIN,
    'META': VK_LWIN,
}

ADB_KEY_MAP = {
    'esc': 'KEYCODE_ESCAPE',
    'enter': 'KEYCODE_ENTER',
    'return': 'KEYCODE_ENTER',
    'space': 'KEYCODE_SPACE',
    'backspace': 'KEYCODE_DEL',
    'delete': 'KEYCODE_FORWARD_DEL',
    'tab': 'KEYCODE_TAB',
    'home': 'KEYCODE_HOME',
    'pageup': 'KEYCODE_PAGE_UP',
    'page_up': 'KEYCODE_PAGE_UP',
    'pagedown': 'KEYCODE_PAGE_DOWN',
    'page_down': 'KEYCODE_PAGE_DOWN',
    'up': 'KEYCODE_DPAD_UP',
    'down': 'KEYCODE_DPAD_DOWN',
    'left': 'KEYCODE_DPAD_LEFT',
    'right': 'KEYCODE_DPAD_RIGHT',
    'alt': 'KEYCODE_ALT_LEFT',
    'lalt': 'KEYCODE_ALT_LEFT',
    'alt_l': 'KEYCODE_ALT_LEFT',
    'ralt': 'KEYCODE_ALT_RIGHT',
    'alt_r': 'KEYCODE_ALT_RIGHT',
    'alt_gr': 'KEYCODE_ALT_RIGHT',
    'ctrl': 'KEYCODE_CTRL_LEFT',
    'control': 'KEYCODE_CTRL_LEFT',
    'lctrl': 'KEYCODE_CTRL_LEFT',
    'lcontrol': 'KEYCODE_CTRL_LEFT',
    'ctrl_l': 'KEYCODE_CTRL_LEFT',
    'rctrl': 'KEYCODE_CTRL_RIGHT',
    'rcontrol': 'KEYCODE_CTRL_RIGHT',
    'ctrl_r': 'KEYCODE_CTRL_RIGHT',
    'shift': 'KEYCODE_SHIFT_LEFT',
    'lshift': 'KEYCODE_SHIFT_LEFT',
    'shift_l': 'KEYCODE_SHIFT_LEFT',
    'rshift': 'KEYCODE_SHIFT_RIGHT',
    'shift_r': 'KEYCODE_SHIFT_RIGHT',
    'capslock': 'KEYCODE_CAPS_LOCK',
    'caps_lock': 'KEYCODE_CAPS_LOCK',
    'numlock': 'KEYCODE_NUM_LOCK',
    'num_lock': 'KEYCODE_NUM_LOCK',
    'scrolllock': 'KEYCODE_SCROLL_LOCK',
    'scroll_lock': 'KEYCODE_SCROLL_LOCK',
    'printscreen': 'KEYCODE_SYSRQ',
    'print_screen': 'KEYCODE_SYSRQ',
}
