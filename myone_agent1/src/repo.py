"""Git 集成：轻量封装 git CLI（借鉴 Aider 的 repo.py）。

只在工作目录内操作，用 subprocess 调 git，不引入 GitPython。
默认仓库目录是 WORKDIR；测试可用临时目录。
"""
import os
import subprocess
from pathlib import Path

from tools import WORKDIR


class GitRepo:
    """对 git CLI 的薄封装：init/add/commit/diff/log。"""

    def __init__(self, repo_dir: Path | str | None = None):
        self.dir = Path(repo_dir or WORKDIR).resolve()

    def _git(self, *args: str) -> str:
        """执行一条 git 命令，返回合并输出；失败抛 RuntimeError。"""
        r = subprocess.run(
            ["git", *args], cwd=self.dir, capture_output=True,
            text=True, encoding="utf-8", errors="replace",
        )
        out = (r.stdout + r.stderr).strip()
        if r.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} 失败：{out}")
        return out

    def is_repo(self) -> bool:
        """当前目录是否已在 git 仓库内。"""
        try:
            self._git("rev-parse", "--is-inside-work-tree")
            return True
        except RuntimeError:
            return False

    def init(self) -> str:
        """初始化仓库（已初始化则幂等返回提示）。"""
        if self.is_repo():
            return "已经是 git 仓库"
        return self._git("init")

    def is_dirty(self) -> bool:
        """是否有未提交的变更。"""
        if not self.is_repo():
            return False
        return bool(self._git("status", "--porcelain").strip())

    def repo_root(self) -> Path | None:
        """定位仓库根目录；不在任何 git 仓库内返回 None。"""
        if not self.is_repo():
            return None
        return Path(self._git("rev-parse", "--show-toplevel")).resolve()

    def rollback(self) -> str:
        """回滚上一次提交（git reset --hard HEAD~1）；无历史时返回提示。"""
        if not self.is_repo():
            return "不是 git 仓库，无法回滚"
        try:
            self._git("reset", "--hard", "HEAD~1")
            return "已回滚上一次提交"
        except RuntimeError as e:
            return f"没有可回滚的提交：{e}"

    def clean(self) -> str:
        """删除所有未跟踪的文件与目录（git clean -fd）。"""
        if not self.is_repo():
            return "不是 git 仓库，无法清理"
        return self._git("clean", "-fd")

    def changed_files(self) -> list[str]:
        """相对 HEAD 的变更文件名；首次提交前返回空。"""
        if not self.is_repo():
            return []
        try:
            out = self._git("diff", "--name-only", "HEAD")
        except RuntimeError:
            return []  # 首个 commit 之前没有 HEAD
        return [ln for ln in out.splitlines() if ln.strip()]

    def diff(self) -> str:
        """未提交的变更内容（用于生成提交消息）。"""
        if not self.is_repo():
            return ""
        try:
            return self._git("diff", "HEAD")
        except RuntimeError:
            return ""

    def _auto_message(self) -> str:
        """从变更文件名生成默认提交消息。"""
        files = self.changed_files()
        if not files:
            return "update"
        names = [f.rsplit("/", 1)[-1] for f in files[:5]]
        return "Update " + ", ".join(names)

    def add(self, *paths: str) -> str:
        """暂存变更（默认全部）。"""
        if not paths:
            paths = ("-A",)
        return self._git("add", *paths)

    def commit(self, message: str | None = None) -> str:
        """提交；没给消息就从变更文件名自动生成。"""
        if not self.is_dirty():
            return "没有可提交的变更"
        self.add()
        msg = message or self._auto_message()
        return self._git("commit", "-m", msg)

    def commit_files(self, paths, message: str | None = None) -> str:
        """只暂存并提交指定路径（保险丝自动提交用）；失败抛 RuntimeError。

        paths 为文件路径列表（Path 或 str）。消息缺省从变更文件名自动生成。
        非 git 仓库、路径为空、或提交失败（如缺 git 身份）时抛 RuntimeError，
        由调用方决定降级，绝不静默吞掉错误。
        """
        if not self.is_repo() or not paths:
            raise RuntimeError("非 git 仓库或无待提交路径")
        add_args = []
        for p in paths:
            rel = os.path.relpath(Path(p).resolve(), self.dir)
            add_args.append(rel.replace(os.sep, "/"))
        self._git("add", *add_args)
        if not self.is_dirty():
            return "没有可提交的变更"
        msg = message or self._auto_message()
        return self._git("commit", "-m", msg)

    def log(self, n: int = 5) -> str:
        """最近 n 条提交的简洁历史。"""
        if not self.is_repo():
            return "（不是 git 仓库）"
        return self._git("log", f"-{n}", "--oneline")

    def remote_url(self) -> str:
        """查看远程地址；未关联返回空字符串。"""
        if not self.is_repo():
            return ""
        try:
            return self._git("remote", "get-url", "origin").strip()
        except RuntimeError:
            return ""

    def remote_set(self, url: str) -> str:
        """关联远程仓库地址（如 https://github.com/用户/项目.git）。"""
        if not self.is_repo():
            self.init()
        if self.remote_url():
            return f"已关联：{self.remote_url()}"
        return self._git("remote", "add", "origin", url)

    def push(self, remote: str = "origin", branch: str = "main") -> str:
        """推送到远程；未关联远程时返回提示而不是报错。"""
        if not self.is_repo():
            return "还不是 git 仓库，先 init"
        if not self.remote_url():
            return "还没有关联远程仓库，先执行 remote_set(url)"
        return self._git("push", "-u", remote, branch)
