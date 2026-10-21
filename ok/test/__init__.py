from ok import DoNothingInteraction
from ok import ImageCaptureMethod
from ok.util.clazz import init_class_by_name

ok = None


def init_ok(config):
    global ok
    if ok is None:
        import os
        os.environ["OK_TEST_MODE"] = "1"
        from ok import OK
        test_config = dict(config)
        test_config['debug'] = True
        test_config['analytics'] = None
        test_config['check_mutex'] = False
        test_config['windows'] = None
        print(f'OKTestRunner init_ok config: {test_config}')
        ok = OK(test_config)
        ok.task_executor.debug_mode = True
        ok.device_manager.capture_method = ImageCaptureMethod(
            ok.device_manager.exit_event, [])
        ok.device_manager.device_dict['image'] = {
            'address': '',
            'imei': 'image',
            'device': 'image',
            'nick': 'Image',
            'width': 0,
            'height': 0,
            'capture': 'image',
            'connected': True,
        }
        ok.device_manager.config['preferred'] = 'image'
        ok.device_manager.interaction = DoNothingInteraction(
            ok.device_manager.capture_method)
        if scene_config := config.get('scene'):
            scene = init_class_by_name(scene_config[0], scene_config[1]) if scene_config else None
            ok.task_executor.scene = scene
            print(f'OKTestRunner scene_config: {scene_config}')
        ok.app
        ok.task_executor.start()


def destroy_ok():
    global ok
    if ok is not None:
        ok.quit()
