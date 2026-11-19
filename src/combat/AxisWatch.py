import ctypes
import threading
import time

try:
    from ok.compat import init_platform_compat
    init_platform_compat()
except ImportError:
    pass

F_VK = 0x46              # 'F'
F_POLL_INTERVAL = 0.05
F_LOG_DEBOUNCE = 1.0
F_TASK_NAME = 'FStartCombatTask'
ENABLE_POLL_INTERVAL = 0.2


def f_settings(task):
    executor = getattr(task, 'executor', None)
    for group in ('trigger_tasks', 'onetime_tasks'):
        for other in getattr(executor, group, None) or ():
            if type(other).__name__ == F_TASK_NAME:
                try:
                    return bool(other.enabled), float(getattr(other, 'f_start_delay', 0) or 0)
                except Exception:
                    return True, 0.0
    return True, 0.0


def start_enable_watch(task, logger=None):
    if getattr(task, '_ww_enable_watch_started', False):
        return
    task._ww_enable_watch_started = True
    if not hasattr(task, '_ww_task_restarted_at'):
        task._ww_task_restarted_at = -1

    def watch():
        was_on = None
        while True:
            try:
                now_on = bool(getattr(task, 'enabled', False))
                if was_on is False and now_on:
                    task._ww_task_restarted_at = time.time()
                    if logger:
                        logger.info('auto combat re-enabled -> opener re-armed')
                was_on = now_on
                time.sleep(ENABLE_POLL_INTERVAL)
            except Exception:
                return

    threading.Thread(target=watch, name='ok_ww_enable_watch', daemon=True).start()


def start_f_watch(task, logger=None):
    if getattr(task, '_f_watch_started', False):
        return
    task._f_watch_started = True
    if not hasattr(task, '_f_last_press'):
        task._f_last_press = -1

    def watch():
        try:
            user32 = ctypes.windll.user32
            user32.GetAsyncKeyState.restype = ctypes.c_short
        except Exception as e:
            task._f_watch_started = False
            if logger:
                logger.error(f'f watch: GetAsyncKeyState unavailable ({e}), '
                             f'the "press F to re-arm the opener" shortcut stays off')
            return
        last_log = 0
        was_down = False
        while True:
            try:
                down = bool(user32.GetAsyncKeyState(F_VK) & 0x8000)
                if down and not was_down and f_settings(task)[0]:
                    now = time.time()
                    if (getattr(task, '_three_fire_macro_busy', False)
                            or getattr(task, '_ww_macro_busy', False)):
                        if logger and now - last_log >= F_LOG_DEBOUNCE:
                            last_log = now
                            logger.info('physical F pressed while the macro is running '
                                        '(manual execution) - opener NOT re-armed')
                        was_down = down
                        time.sleep(F_POLL_INTERVAL)
                        continue
                    task._f_last_press = now
                    task._f_pressed_at = now
                    if logger and now - last_log >= F_LOG_DEBOUNCE:
                        last_log = now
                        logger.info('physical F pressed, opener re-armed')
                was_down = down
                time.sleep(F_POLL_INTERVAL)
            except Exception:
                return

    threading.Thread(target=watch, name='ok_ww_f_watch', daemon=True).start()
