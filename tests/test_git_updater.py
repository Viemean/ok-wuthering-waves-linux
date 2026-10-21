import unittest
from unittest.mock import MagicMock, patch

from ok.util.git_updater import (
    DEFAULT_BRANCH,
    DEFAULT_UPSTREAM_URL,
    check_git_updates,
    get_current_branch,
    get_current_commit,
    get_git_root,
    is_git_repository,
    pull_git_updates,
    restart_with_uv,
)


class TestGitUpdater(unittest.TestCase):

    @patch("subprocess.check_output", return_value="/dummy/repo\n")
    @patch("os.path.isdir", return_value=True)
    def test_get_git_root(self, mock_isdir, mock_output):
        root = get_git_root("/dummy/cwd")
        self.assertEqual("/dummy/repo", root)
        self.assertTrue(is_git_repository("/dummy/cwd"))

    @patch("ok.util.git_updater.get_git_root", return_value="/dummy/repo")
    @patch("subprocess.check_output", return_value="abc1234\n")
    def test_get_current_commit(self, mock_output, mock_root):
        commit = get_current_commit()
        self.assertEqual("abc1234", commit)

    @patch("ok.util.git_updater.get_git_root", return_value="/dummy/repo")
    @patch("subprocess.check_output", return_value="linux-support\n")
    def test_get_current_branch(self, mock_output, mock_root):
        branch = get_current_branch()
        self.assertEqual("linux-support", branch)

    @patch("ok.util.git_updater.get_git_root", return_value="/dummy/repo")
    @patch("ok.util.git_updater.get_current_branch", return_value="linux-support")
    @patch("ok.util.git_updater.get_current_commit", return_value="commit_local")
    @patch("subprocess.check_call")
    @patch("subprocess.check_output")
    def test_check_git_updates_already_up_to_date(self, mock_output, mock_call, mock_commit, mock_branch, mock_root):
        mock_output.return_value = "commit_local\n"
        has_update, notes, info = check_git_updates()
        self.assertFalse(has_update)
        self.assertEqual([], notes)
        self.assertEqual("Already up to date", info)

    @patch("ok.util.git_updater.get_git_root", return_value="/dummy/repo")
    @patch("ok.util.git_updater.get_current_branch", return_value="linux-support")
    @patch("ok.util.git_updater.get_current_commit", return_value="commit_local")
    @patch("subprocess.check_call")
    @patch("subprocess.check_output")
    def test_check_git_updates_has_new_commits(self, mock_output, mock_call, mock_commit, mock_branch, mock_root):
        def side_effect(cmd, **kwargs):
            if cmd[1] == "rev-parse":
                return "commit_remote\n"
            if cmd[1] == "log":
                return "c1 commit 1\nc2 commit 2\n"
            return ""

        mock_output.side_effect = side_effect
        has_update, notes, info = check_git_updates()
        self.assertTrue(has_update)
        self.assertEqual(["c1 commit 1", "c2 commit 2"], notes)
        self.assertEqual("commit_remote", info)

    @patch("ok.util.git_updater.get_git_root", return_value="/dummy/repo")
    @patch("ok.util.git_updater.get_current_branch", return_value="linux-support")
    @patch("subprocess.check_call")
    def test_pull_git_updates_success(self, mock_call, mock_branch, mock_root):
        success, msg = pull_git_updates()
        self.assertTrue(success)
        self.assertEqual("Success", msg)
        self.assertEqual(2, mock_call.call_count)

    @patch("ok.util.git_updater.get_git_root", return_value="/dummy/repo")
    @patch("ok.util.git_updater.get_current_commit", return_value="c1_full")
    @patch("subprocess.check_output", return_value="c1_full|c1|commit 1\nc2_full|c2|commit 2\n")
    def test_get_local_commits(self, mock_output, mock_head, mock_root):
        from ok.util.git_updater import get_local_commits
        commits = get_local_commits()
        self.assertEqual(2, len(commits))
        self.assertEqual("c1", commits[0]["short_hash"])
        self.assertTrue(commits[0]["is_head"])
        self.assertFalse(commits[1]["is_head"])

    @patch("ok.util.git_updater.get_git_root", return_value="/dummy/repo")
    @patch("ok.util.git_updater.get_current_branch", return_value="linux-support")
    @patch("subprocess.check_call")
    def test_pull_git_updates_target_commit(self, mock_call, mock_branch, mock_root):
        success, msg = pull_git_updates(target_commit="c2_full")
        self.assertTrue(success)
        self.assertEqual("Success", msg)
        mock_call.assert_called_once_with(
            ["git", "reset", "--hard", "c2_full"],
            cwd="/dummy/repo",
            stdout=-3,
            stderr=-3,
        )

    @patch("ok.util.git_updater.get_git_root", return_value="/dummy/repo")
    @patch("shutil.which", return_value="/usr/bin/uv")
    @patch("subprocess.Popen")
    @patch("os._exit")
    def test_restart_with_uv(self, mock_exit, mock_popen, mock_which, mock_root):
        restart_with_uv()
        mock_popen.assert_called_once()
        args, kwargs = mock_popen.call_args
        self.assertEqual("/usr/bin/uv", args[0][0])
        self.assertEqual("run", args[0][1])
        self.assertEqual("python", args[0][2])
        self.assertEqual("main.py", args[0][3])
        mock_exit.assert_called_once_with(0)


if __name__ == "__main__":
    unittest.main()
