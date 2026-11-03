from ok import BrowserInteraction, PostMessageInteraction
from src.task.MouseResetTask import MouseResetTask


class WWOneTimeTask:

    def run(self):
        # Reset interrupted rotations on the executor before startup can sleep.
        if hasattr(self, 'reset_combat_state'):
            self.reset_combat_state('onetime task start')
        # [LINUX-PORT-CRITICAL] Linux 分支专属核心适配：防止任务未挂载或获取失败时抛出 AttributeError
        mouse_reset_task = self.executor.get_task_by_class(MouseResetTask)
        if mouse_reset_task is not None:
            mouse_reset_task.run()
        if isinstance(self.executor.interaction, PostMessageInteraction):
            self.executor.interaction.activate()
        self.sleep(0.5)
