from PySide6.QtCore import QEvent, QRect
from qfluentwidgets.components.widgets.spin_box import SpinBoxBase, InlineSpinBoxBase


def patch_spin_box():
    if getattr(SpinBoxBase, '_ok_patched', False):
        return
    SpinBoxBase._ok_patched = True

    def _update_line_edit_geometry(sb):
        le = sb.lineEdit()
        if le is None:
            return
        right_margin = 82 if isinstance(sb, InlineSpinBoxBase) else 30
        if hasattr(sb, 'property') and sb.property('symbolVisible') is False:
            right_margin = 10
        left_margin = 10
        top = 2
        height = max(0, sb.height() - 4)
        width = max(0, sb.width() - left_margin - right_margin)
        le.setGeometry(QRect(left_margin, top, width, height))

    def _spin_box_base_event(self, e):
        res = super(SpinBoxBase, self).event(e)
        if e.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Show,
            QEvent.Type.LayoutRequest,
            QEvent.Type.StyleChange,
            QEvent.Type.Polish,
        ):
            _update_line_edit_geometry(self)
        return res

    SpinBoxBase.event = _spin_box_base_event
