from ok import BrowserInteraction, PostMessageInteraction


class WWOneTimeTask:

    def run(self):
        if isinstance(self.executor.interaction, PostMessageInteraction):
            self.executor.interaction.activate()
        self.sleep(0.5)
