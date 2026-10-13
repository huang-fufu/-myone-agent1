"""repo.py Git 集成测试：临时目录建真实 git 仓库验证（借鉴 Aider 的 test_repo.py）。

本机没有 git 时整组跳过，不影响其它测试。
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

from repo import GitRepo

GIT_AVAILABLE = shutil.which("git") is not None


@unittest.skipUnless(GIT_AVAILABLE, "本机没有 git")
class TestGitRepo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.repo = GitRepo(self.tmp)
        self.repo.init()
        # 配置仓库内身份（git commit 必需），并建一个初始提交
        self.repo._git("config", "user.name", "tester")
        self.repo._git("config", "user.email", "tester@example.com")
        (Path(self.tmp) / "demo.txt").write_text("v1", encoding="utf-8")
        self.repo.add()
        self.repo.commit("initial")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_is_repo(self):
        self.assertTrue(self.repo.is_repo())

    def test_dirty_after_edit(self):
        (Path(self.tmp) / "demo.txt").write_text("v2", encoding="utf-8")
        self.assertTrue(self.repo.is_dirty())

    def test_commit_auto_message(self):
        """不传消息时，自动从变更文件名生成提交消息。"""
        (Path(self.tmp) / "a.py").write_text("x = 1", encoding="utf-8")
        msg = self.repo.commit()
        self.assertIn("a.py", msg)
        self.assertFalse(self.repo.is_dirty())

    def test_log_shows_commits(self):
        out = self.repo.log(5)
        self.assertIn("initial", out)

    def test_not_a_repo_outside(self):
        self.assertFalse(GitRepo(tempfile.mkdtemp()).is_repo())

    def test_remote_set_and_url(self):
        """remote_set 关联后，remote_url 应能读回同一地址。"""
        self.repo.remote_set("https://github.com/huang-fufu/demo.git")
        self.assertEqual(self.repo.remote_url(), "https://github.com/huang-fufu/demo.git")

    def test_remote_set_idempotent(self):
        """重复 remote_set 应返回"已关联"提示而不是覆盖/报错。"""
        self.repo.remote_set("https://github.com/huang-fufu/demo.git")
        out = self.repo.remote_set("https://github.com/huang-fufu/other.git")
        self.assertIn("已关联", out)
        self.assertEqual(self.repo.remote_url(), "https://github.com/huang-fufu/demo.git")

    def test_push_without_remote_returns_hint(self):
        """未关联远程时 push 应返回提示而不是抛异常。"""
        out = self.repo.push()
        self.assertIn("还没有关联远程仓库", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
