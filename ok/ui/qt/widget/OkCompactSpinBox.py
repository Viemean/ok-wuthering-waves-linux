from qfluentwidgets.components.widgets.spin_box import CompactSpinBox, SpinBoxBase

from ok.ui.qt.widget.spin_box import patch_spin_box

patch_spin_box()


class OkCompactSpinBox(CompactSpinBox):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def focusInEvent(self, e):
        super(SpinBoxBase, self).focusInEvent(e)
