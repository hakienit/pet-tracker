"""Test `_git` / `git_state` / `_remote_has_head` với git thật trong repo tạm: không chạy mã từ config repo,
không bị GIT_* làm lệch, không đọc config toàn cục của người dùng. Kỹ thuật "file đánh dấu": script do repo cấu
hình mà chạy thì tạo marker, test khẳng định marker không tồn tại."""
import http.server
import os
import shutil
import ssl
import stat
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from pet_tracker import session_ops

_ID = ["-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false"]


def _env():
    # GIT_* kế thừa không được lái git của test; config toàn cục/hệ thống của người dùng không được lọt vào repo tạm
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    return env


def run(cwd, *args):
    subprocess.run(["git", *_ID, *args], cwd=cwd, env=_env(), check=True, capture_output=True)


def script(path: Path, marker: Path, out: str = ""):
    """Script tạo `marker` rồi (tuỳ chọn) in `out` ra stdout."""
    path.write_text(f"#!/bin/sh\ncat >/dev/null 2>&1 </dev/null\ntouch '{marker}'\nprintf '{out}'\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


class _Deny(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="x"')
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *a):
        pass


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(os.path.realpath(self._tmp.name))
        # `_git` bỏ mọi GIT_*, nên cách duy nhất để cô lập config toàn cục của người dùng là đổi HOME
        home = self.root / "home"
        home.mkdir()
        p = mock.patch.dict(os.environ, {"HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config"),
                                         "USERPROFILE": str(home)})
        p.start()
        self.addCleanup(p.stop)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        run(self.repo, "init", "-q", "-b", "main")
        (self.repo / "a.txt").write_text("a")
        run(self.repo, "add", "a.txt")
        run(self.repo, "commit", "-q", "-m", "init")
        self.marker = self.root / "ran"


class GitTest(Base):
    def test_state_clean_and_untracked(self):
        st = session_ops.git_state(str(self.repo))
        self.assertEqual(st["top"], str(self.repo))
        self.assertEqual(st["common"], str(self.repo / ".git"))
        self.assertEqual((st["branch"], st["dirty"], st["linked"]), ("main", 0, False))
        (self.repo / "new.txt").write_text("x")
        self.assertEqual(session_ops.git_state(str(self.repo))["dirty"], 1)

    def test_linked_worktree(self):
        wt = self.root / "wt"
        run(self.repo, "worktree", "add", "-q", "-b", "feat", str(wt))
        st = session_ops.git_state(str(wt))
        self.assertEqual(st["top"], str(wt))
        self.assertEqual(st["common"], str(self.repo / ".git"))
        self.assertTrue(st["linked"])
        self.assertEqual(st["branch"], "feat")

    def test_fsmonitor_not_executed(self):
        script(self.root / "fsm.sh", self.marker)
        run(self.repo, "config", "core.fsmonitor", str(self.root / "fsm.sh"))
        self.assertIsNotNone(session_ops.git_state(str(self.repo)))
        self.assertFalse(self.marker.exists())

    def test_hooks_not_executed(self):
        hooks = self.root / "hooks"
        hooks.mkdir()
        for name in ("post-checkout", "reference-transaction", "pre-commit", "post-merge"):
            script(hooks / name, self.marker)
        run(self.repo, "branch", "old")  # tạo trước khi bật hooksPath: lệnh của test không được kích hook
        run(self.repo, "config", "core.hooksPath", str(hooks))
        # lệnh ghi ref / checkout: nơi hook chạy; đi qua đúng đường _git như remove_worktree
        rc, out = session_ops._git(self.repo, "branch", "-d", "old")
        self.assertEqual(rc, 0, out)
        wt = self.root / "wt"
        rc, out = session_ops._git(self.repo, "worktree", "add", "-b", "feat", str(wt))
        self.assertEqual(rc, 0, out)
        session_ops.git_state(str(wt))
        self.assertFalse(self.marker.exists())

    def test_inherited_git_env_ignored(self):
        other = self.root / "other"
        other.mkdir()
        run(other, "init", "-q", "-b", "other")
        saved = {k: os.environ.get(k) for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_CONFIG_PARAMETERS")}
        self.addCleanup(lambda: [os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
                                 for k, v in saved.items()])
        os.environ["GIT_DIR"] = str(other / ".git")
        os.environ["GIT_WORK_TREE"] = str(other)
        os.environ["GIT_CONFIG_PARAMETERS"] = "'core.bare=true'"
        st = session_ops.git_state(str(self.repo))
        self.assertEqual((st["top"], st["branch"]), (str(self.repo), "main"))

    def test_env_and_stdin(self):
        # prompt credential không thể test kín (cần tty): kiểm tận gốc, env/stdin truyền cho git
        with mock.patch.dict(os.environ, {"GIT_DIR": "/x", "GIT_ASKPASS": "y", "git_ssh": "z"}), \
                mock.patch.object(session_ops.subprocess, "run") as m:
            m.return_value = mock.Mock(returncode=0, stdout="", stderr="")
            session_ops._git(self.repo, "status")
        env, argv = m.call_args.kwargs["env"], m.call_args.args[0]
        self.assertEqual({k for k in env if k.upper().startswith("GIT_")}, {"GIT_TERMINAL_PROMPT"})
        self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")
        self.assertIs(m.call_args.kwargs["stdin"], subprocess.DEVNULL)
        self.assertIn("--no-optional-locks", argv)


class FilterTest(Base):
    """Filter driver clean/smudge/process chạy khi `status` thấy stat lệch (git_state, worktree remove)."""

    def _setup_filter(self, wt: Path):
        (wt / ".gitattributes").write_text("*.txt filter=x filter=p\n")
        run(wt, "add", ".gitattributes")
        run(wt, "commit", "-q", "-m", "attr")
        return wt

    def _arm(self, wt: Path):
        clean = script(self.root / "clean.sh", self.marker)
        clean.write_text(f"#!/bin/sh\ntouch '{self.marker}'\ncat\n")
        run(self.repo, "config", "filter.x.clean", str(clean))
        run(self.repo, "config", "filter.p.process", str(clean))
        os.utime(wt / "a.txt", (1, 1))  # stat lệch với index: git băm lại file, đi qua clean filter

    def test_state_does_not_run_filter(self):
        self._setup_filter(self.repo)
        self._arm(self.repo)
        st = session_ops.git_state(str(self.repo))
        self.assertEqual(st["dirty"], 0)
        self.assertFalse(self.marker.exists())

    def _linked(self):
        self._setup_filter(self.repo)
        wt = self.root / "wt"
        run(self.repo, "worktree", "add", "-q", "-b", "feat", str(wt))
        return wt

    def test_remove_worktree_does_not_run_filter(self):
        wt = self._linked()
        self._arm(wt)
        ok, msg = session_ops.remove_worktree({"cwd": str(wt), "session_id": "s"}, str(self.root / "claude"))
        self.assertTrue(ok, msg)
        self.assertFalse(wt.exists())
        self.assertFalse(self.marker.exists())

    def test_worktree_remove_itself_does_not_run_filter(self):
        # git_state bơm sẵn (tính trước khi cài filter): chỉ còn status bên trong `worktree remove`
        wt = self._linked()
        st = session_ops.git_state(str(wt))
        self._arm(wt)
        with mock.patch.object(session_ops, "git_state", return_value=st):
            ok, msg = session_ops.remove_worktree({"cwd": str(wt), "session_id": "s"}, str(self.root / "claude"))
        self.assertTrue(ok, msg)
        self.assertFalse(self.marker.exists())

    def test_filter_names_from_config(self):
        for k in ("filter.ok.clean", "filter.d.e.smudge"):
            run(self.repo, "config", k, "x")
        run(self.repo, "config", "filter.ok.required", "true")  # không thuộc regexp: bỏ qua
        args = session_ops._filters_off(self.repo)
        self.assertEqual(args[0::2], ["-c"] * (len(args) // 2))
        self.assertEqual(set(args[1::2]), {"filter.ok.clean=", "filter.ok.smudge=", "filter.ok.process=",
                                           "filter.ok.required=false", "filter.d.e.clean=", "filter.d.e.smudge=",
                                           "filter.d.e.process=", "filter.d.e.required=false"})

    def test_no_filters_is_empty_not_none(self):
        self.assertEqual(session_ops._filters_off(self.repo), [])

    def test_unsafe_name_is_none(self):
        for i, name in enumerate(("a=b", "a\x01b", "a b", "a\tb")):
            with self.subTest(name=name):
                cfg = self.repo / ".git" / "config"
                cfg.write_text(cfg.read_text() + f'[filter "{name}"]\n\tclean = x\n')
                self.assertIsNone(session_ops._filters_off(self.repo))
                cfg.write_text(cfg.read_text().rsplit("[filter", 1)[0])  # dọn cho vòng sau
                self.assertEqual(session_ops._filters_off(self.repo), [])

    def _unsafe(self, wt: Path, name: str):
        """Filter tên không diễn tả được bằng `-c`, bật qua .git/info/attributes (không cần commit)."""
        clean = self.root / "clean.sh"
        clean.write_text(f"#!/bin/sh\ntouch '{self.marker}'\ncat\n")
        clean.chmod(clean.stat().st_mode | stat.S_IXUSR)
        info = Path(subprocess.check_output(["git", "rev-parse", "--git-common-dir"], cwd=wt, text=True,
                                            env=_env()).strip())
        info = (info if info.is_absolute() else wt / info) / "info"
        info.mkdir(exist_ok=True)
        (info / "attributes").write_bytes(f"*.txt filter={name}\n".encode())
        cfg = (info.parent / "config")
        cfg.write_text(cfg.read_text() + f'[filter "{name}"]\n\tclean = {clean}\n')
        os.utime(wt / "a.txt", (1, 1))

    def test_state_fails_closed_on_unsafe_name(self):
        for name in ("a=b", "a\x01b"):
            with self.subTest(name=name):
                self._unsafe(self.repo, name)
                st = session_ops.git_state(str(self.repo))
                self.assertFalse(self.marker.exists())
                self.assertIsNone(st)

    def test_remove_refuses_on_unsafe_name(self):
        for i, name in enumerate(("a=b", "a\x01b")):
            with self.subTest(name=name):
                wt = self.root / f"wt{i}"
                run(self.repo, "worktree", "add", "-q", "-b", f"f{i}", str(wt))
                st = session_ops.git_state(str(wt))
                self.assertTrue(st["done"])
                self._unsafe(wt, name)
                with mock.patch.object(session_ops, "git_state", return_value=st):
                    ok, msg = session_ops.remove_worktree({"cwd": str(wt), "session_id": "s"},
                                                           str(self.root / "claude"))
                self.assertFalse(ok)
                self.assertIn("filter", msg)
                self.assertTrue(wt.exists())
                self.assertFalse(self.marker.exists())
                cfg = self.repo / ".git" / "config"  # dọn cho vòng sau
                cfg.write_text(cfg.read_text().rsplit("[filter", 1)[0])


class RemoteTest(Base):
    """`ls-remote` trong `_remote_has_head` không được chạy mã do config repo khai báo."""

    def setUp(self):
        super().setUp()
        self.other = self.root / "other"  # repo cục bộ làm "remote"
        self.other.mkdir()
        run(self.other, "init", "-q", "-b", "main")
        run(self.other, "commit", "-q", "--allow-empty", "-m", "o")
        self.st = {"branch": "main", "top": str(self.repo)}

    def _branch(self, remote="origin", merge="refs/heads/main"):
        run(self.repo, "config", "branch.main.remote", remote)
        run(self.repo, "config", "branch.main.merge", merge)

    def _probe(self):
        with mock.patch.object(session_ops, "_git", wraps=session_ops._git) as g:
            res = session_ops._remote_has_head(self.st)
        self.calls = [c.args for c in g.call_args_list]
        self.opts = [c.kwargs.get("opts", ()) for c in g.call_args_list if "ls-remote" in c.args]
        return res

    def _check(self, url, **cfg):
        run(self.repo, "config", "remote.origin.url", url)
        self._branch()
        # repo cố mở mọi giao thức: cờ per-protocol của _git phải thắng (cờ chung protocol.allow không đủ)
        for x in ("ext", "file", "git", "fd"):
            run(self.repo, "config", f"protocol.{x}.allow", "always")
        for k, v in cfg.items():
            run(self.repo, "config", k.replace("__", "."), v)
        self.assertFalse(self._probe())
        self.assertFalse(self.marker.exists())

    def test_ext_transport(self):
        s = script(self.root / "ext.sh", self.marker)
        self._check(f"ext::{s} x")

    def test_ssh_command(self):
        s = script(self.root / "ssh.sh", self.marker)
        self._check("ssh://127.0.0.1:1/x", core__sshCommand=str(s))

    def test_uploadpack_local_remote(self):
        s = script(self.root / "up.sh", self.marker)
        self._check(str(self.other), remote__origin__uploadpack=str(s))

    def test_git_proxy(self):
        s = script(self.root / "proxy.sh", self.marker)
        self._check("git://127.0.0.1:1/x", core__gitProxy=str(s))

    def test_include_path(self):
        s = script(self.root / "inc.sh", self.marker)
        inc = self.root / "inc.cfg"
        inc.write_text(f"[core]\n\tsshCommand = {s}\n[remote \"origin\"]\n\tuploadpack = {s}\n"
                       f"[core]\n\tgitProxy = {s}\n")
        self._check("ssh://127.0.0.1:1/x", include__path=str(inc))

    def test_include_path_uploadpack_local(self):
        s = script(self.root / "inc.sh", self.marker)
        inc = self.root / "inc.cfg"
        inc.write_text(f"[remote \"origin\"]\n\tuploadpack = {s}\n")
        self._check(str(self.other), include__path=str(inc))

    def _serve(self):
        """Server https cục bộ luôn đòi đăng nhập (401); repo tin chứng chỉ tự ký qua http.sslCAInfo."""
        if not shutil.which("openssl"):
            self.skipTest("cần openssl để dựng server https cục bộ")
        crt, key = self.root / "c.pem", self.root / "k.pem"
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", "/CN=127.0.0.1",
                        "-addext", "subjectAltName=IP:127.0.0.1", "-keyout", str(key), "-out", str(crt)],
                       check=True, capture_output=True)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(crt, key)
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Deny)
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
        run(self.repo, "config", "http.sslCAInfo", str(crt))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (srv.shutdown(), srv.server_close()))
        return f"https://127.0.0.1:{srv.server_address[1]}/r.git"

    def test_credential_helper(self):
        s = script(self.root / "cred.sh", self.marker, out="username=u\\npassword=p\\n")
        self._check(self._serve(), credential__helper=f"!{s}")
        self.assertIn("credential.helper=", self.opts[0])

    def test_askpass(self):
        s = script(self.root / "ask.sh", self.marker, out="x")
        self._check(self._serve(), core__askPass=str(s))
        self.assertIn("core.askPass=", self.opts[0])

    def test_option_injection_remote(self):
        s = script(self.root / "inj.sh", self.marker)
        self._branch(remote=f"--upload-pack={s}")
        self.assertFalse(self._probe())
        self.assertFalse(self.marker.exists())
        self.assertFalse(any("ls-remote" in c for c in self.calls))

    def test_option_injection_merge(self):
        s = script(self.root / "inj.sh", self.marker)
        run(self.repo, "config", "remote.origin.url", str(self.other))
        self._branch(merge=f"--upload-pack={s}")
        self.assertFalse(self._probe())
        self.assertFalse(self.marker.exists())
        self.assertFalse(any("ls-remote" in c for c in self.calls))


if __name__ == "__main__":
    unittest.main()
