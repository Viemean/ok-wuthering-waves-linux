import unittest
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

from ok.ui.qt.about.UpdateCard import UpdateCard

app = QApplication.instance() or QApplication([])


class TestUpdateCardGit(unittest.TestCase):

    def setUp(self):
        self.pyappify_mock = MagicMock()
        self.card = UpdateCard("v1.0.0", self.pyappify_mock)

    def test_test_version_checkbox_removed(self):
        self.assertFalse(hasattr(self.card, "test_version_checkbox"))

    @patch("ok.ui.qt.about.UpdateCard.is_git_repository", return_value=True)
    @patch("ok.ui.qt.about.UpdateCard.check_git_updates")
    def test_check_for_updates_git_triggers_background(self, mock_check, mock_is_git):
        with patch.object(self.card, "_run_in_background") as mock_run:
            self.card.check_for_updates()
            mock_run.assert_called_once()
            args = mock_run.call_args[0]
            self.assertEqual(mock_check, args[0])

    def test_apply_git_check_result_no_update(self):
        self.card._apply_git_check_result((True, (False, [], "Already up to date")))
        self.assertFalse(self.card.update_button.isEnabled())
        self.assertEqual(self.card.tr("Current version"), self.card.update_button.text())

    def test_apply_git_check_result_with_update(self):
        notes = ["commit 1", "commit 2"]
        self.card._apply_git_check_result((True, (True, notes, "commit_hash")))
        self.assertTrue(self.card.update_button.isEnabled())
        self.assertEqual(self.card.tr("Update"), self.card.update_button.text())
        self.assertIn("commit 1", self.card.notes_edit.toPlainText())

    @patch("ok.ui.qt.about.UpdateCard.is_git_repository", return_value=True)
    @patch("ok.ui.qt.about.UpdateCard.pull_git_updates")
    def test_update_to_selected_version_git(self, mock_pull, mock_is_git):
        with patch.object(self.card, "_run_in_background") as mock_run:
            self.card.update_to_selected_version()
            mock_run.assert_called_once()
            args = mock_run.call_args[0]
            # args[0] is the lambda executing pull_git_updates
            args[0]()
            mock_pull.assert_called_once_with(target_commit=None)

    def test_status_label_not_word_wrapped(self):
        self.assertFalse(self.card.status_label.wordWrap())

    def test_select_version_button_exists(self):
        self.assertTrue(hasattr(self.card, "select_version_button"))

    def test_on_version_selected_different_commit(self):
        commit_item = {
            "hash": "commit_other",
            "short_hash": "c_other",
            "message": "other commit",
            "is_head": False,
        }
        self.card._on_version_selected(commit_item)
        self.assertEqual("commit_other", self.card.target_git_commit)
        self.assertTrue(self.card.update_button.isEnabled())
        self.assertEqual(self.card.tr("Switch"), self.card.update_button.text())

    def test_on_version_selected_head_commit(self):
        commit_item = {
            "hash": "commit_head",
            "short_hash": "c_head",
            "message": "head commit",
            "is_head": True,
        }
        self.card._on_version_selected(commit_item)
        self.assertEqual("commit_head", self.card.target_git_commit)
        self.assertFalse(self.card.update_button.isEnabled())
        self.assertEqual(self.card.tr("Current version"), self.card.update_button.text())


if __name__ == "__main__":
    unittest.main()
