"""Platform compatibility layer for ok-script on non-Windows systems."""
import sys
import ctypes
import types


class _WindowsStub:
    """A callable, chainable stub for Windows API attributes and constants."""

    def __getattr__(self, name):
        if name.startswith('__') and name.endswith('__'):
            raise AttributeError(name)
        return _WindowsStub()

    def __call__(self, *args, **kwargs):
        return 0

    def __int__(self):
        return 0

    def __bool__(self):
        return False

    def __iter__(self):
        return iter([])


WIN32CON_CONSTANTS = {
    # Virtual Key Codes
    'VK_LBUTTON': 0x01, 'VK_RBUTTON': 0x02, 'VK_CANCEL': 0x03, 'VK_MBUTTON': 0x04,
    'VK_BACK': 0x08, 'VK_TAB': 0x09, 'VK_CLEAR': 0x0C, 'VK_RETURN': 0x0D,
    'VK_SHIFT': 0x10, 'VK_CONTROL': 0x11, 'VK_MENU': 0x12, 'VK_PAUSE': 0x13,
    'VK_CAPITAL': 0x14, 'VK_ESCAPE': 0x1B, 'VK_SPACE': 0x20,
    'VK_PRIOR': 0x21, 'VK_NEXT': 0x22, 'VK_END': 0x23, 'VK_HOME': 0x24,
    'VK_LEFT': 0x25, 'VK_UP': 0x26, 'VK_RIGHT': 0x27, 'VK_DOWN': 0x28,
    'VK_SELECT': 0x29, 'VK_PRINT': 0x2A, 'VK_EXECUTE': 0x2B, 'VK_SNAPSHOT': 0x2C,
    'VK_INSERT': 0x2D, 'VK_DELETE': 0x2E, 'VK_HELP': 0x2F,
    'VK_LWIN': 0x5B, 'VK_RWIN': 0x5C, 'VK_APPS': 0x5D, 'VK_SLEEP': 0x5F,
    'VK_NUMPAD0': 0x60, 'VK_NUMPAD1': 0x61, 'VK_NUMPAD2': 0x62, 'VK_NUMPAD3': 0x63,
    'VK_NUMPAD4': 0x64, 'VK_NUMPAD5': 0x65, 'VK_NUMPAD6': 0x66, 'VK_NUMPAD7': 0x67,
    'VK_NUMPAD8': 0x68, 'VK_NUMPAD9': 0x69, 'VK_MULTIPLY': 0x6A, 'VK_ADD': 0x6B,
    'VK_SEPARATOR': 0x6C, 'VK_SUBTRACT': 0x6D, 'VK_DECIMAL': 0x6E, 'VK_DIVIDE': 0x6F,
    'VK_F1': 0x70, 'VK_F2': 0x71, 'VK_F3': 0x72, 'VK_F4': 0x73,
    'VK_F5': 0x74, 'VK_F6': 0x75, 'VK_F7': 0x76, 'VK_F8': 0x77,
    'VK_F9': 0x78, 'VK_F10': 0x79, 'VK_F11': 0x7A, 'VK_F12': 0x7B,
    'VK_NUMLOCK': 0x90, 'VK_SCROLL': 0x91,
    'VK_LSHIFT': 0xA0, 'VK_RSHIFT': 0xA1, 'VK_LCONTROL': 0xA2, 'VK_RCONTROL': 0xA3,
    'VK_LMENU': 0xA4, 'VK_RMENU': 0xA5,

    # Window Messages
    'WM_ACTIVATE': 0x0006, 'WA_INACTIVE': 0, 'WA_ACTIVE': 1, 'WA_CLICKACTIVE': 2,
    'WM_SETFOCUS': 0x0007, 'WM_KILLFOCUS': 0x0008, 'WM_ENABLE': 0x000A,
    'WM_PAINT': 0x000F, 'WM_CLOSE': 0x0010, 'WM_QUIT': 0x0012,
    'WM_ACTIVATEAPP': 0x001C, 'WM_NCACTIVATE': 0x0086,
    'WM_KEYDOWN': 0x0100, 'WM_KEYUP': 0x0101, 'WM_CHAR': 0x0102,
    'WM_SYSKEYDOWN': 0x0104, 'WM_SYSKEYUP': 0x0105,
    'WM_MOUSEMOVE': 0x0200, 'WM_LBUTTONDOWN': 0x0201, 'WM_LBUTTONUP': 0x0202,
    'WM_RBUTTONDOWN': 0x0204, 'WM_RBUTTONUP': 0x0205,
    'WM_MBUTTONDOWN': 0x0207, 'WM_MBUTTONUP': 0x0208,
    'WM_MOUSEWHEEL': 0x020A,
    'MK_LBUTTON': 0x0001, 'MK_RBUTTON': 0x0002, 'MK_SHIFT': 0x0004,
    'MK_CONTROL': 0x0008, 'MK_MBUTTON': 0x0010,
    'WHEEL_DELTA': 120,

    # Show Window Flags
    'SW_HIDE': 0, 'SW_NORMAL': 1, 'SW_SHOWNORMAL': 1, 'SW_SHOWMINIMIZED': 2,
    'SW_MAXIMIZE': 3, 'SW_SHOWMAXIMIZED': 3, 'SW_SHOWNOACTIVATE': 4,
    'SW_SHOW': 5, 'SW_MINIMIZE': 6, 'SW_SHOWMINNOACTIVE': 7,
    'SW_SHOWNA': 8, 'SW_RESTORE': 9, 'SW_SHOWDEFAULT': 10,

    # Window Style & SetWindowPos
    'GWL_STYLE': -16, 'GWL_EXSTYLE': -20, 'GW_HWNDNEXT': 2,
    'WS_CAPTION': 0x00C00000, 'WS_POPUP': 0x80000000,
    'SWP_NOSIZE': 0x0001, 'SWP_NOMOVE': 0x0002, 'SWP_NOZORDER': 0x0004,
    'SWP_FRAMECHANGED': 0x0020, 'SWP_SHOWWINDOW': 0x0040,
    'HWND_TOPMOST': -1, 'HWND_NOTOPMOST': -2,
    'SM_CXSCREEN': 0, 'SM_CYSCREEN': 1,
    'MONITOR_DEFAULTTONEAREST': 2,
    'SRCCOPY': 0x00CC0020,
}


def init_platform_compat():
    """Initialize platform stubs when running on non-Windows operating systems."""
    if sys.platform == 'win32':
        return

    if not hasattr(ctypes, 'windll'):
        ctypes.windll = _WindowsStub()
    if not hasattr(ctypes, 'WinDLL'):
        ctypes.WinDLL = lambda *args, **kwargs: _WindowsStub()

    windows_modules = [
        'win32api',
        'win32con',
        'win32gui',
        'win32ui',
        'win32process',
        'win32clipboard',
        'win32event',
        'winsound',
    ]
    for mod in windows_modules:
        if mod not in sys.modules:
            m = types.ModuleType(mod)
            if mod == 'win32con':
                for k, v in WIN32CON_CONSTANTS.items():
                    setattr(m, k, v)
                stub = _WindowsStub()
                m.__getattr__ = lambda name, s=stub, c=WIN32CON_CONSTANTS: c.get(name, s.__getattr__(name))
            else:
                m.__getattr__ = _WindowsStub().__getattr__
            sys.modules[mod] = m
