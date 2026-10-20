from qfluentwidgets import BodyLabel

from ok import og
from ok.ui.qt.tasks.ConfigLabelAndWidget import ConfigLabelAndWidget


class LabelAndReadOnly(ConfigLabelAndWidget):

    def __init__(self, config_desc, config, key: str, options=None):
        super().__init__(config_desc, config, key)
        self.key = key
        val = str(self.config.get(self.key) or "")
        tr_val = og.app.tr(val) if og.app and hasattr(og.app, 'tr') else val
        self.label = BodyLabel(tr_val)
        self.add_widget(self.label, stretch=0)

    def update_value(self):
        val = str(self.config.get(self.key) or "")
        tr_val = og.app.tr(val) if og.app and hasattr(og.app, 'tr') else val
        self.label.setText(tr_val)
