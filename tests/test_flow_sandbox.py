"""The bwrap sandbox for real: no network, no key, capped size, output, time and scope."""

from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path

import pytest

from agency.agents.toolbox import Toolbox
from agency.contracts.secrets import API_KEY_VARIABLES
from agency.workshop.sandbox import (
    JOB,
    MEMORY_MAX_BYTES,
    OUTPUT_BYTES,
    SHM_BYTES,
    TASKS_MAX,
    Completed,
    Sandbox,
    SandboxUnavailable,
)
from support.flow import bare_context


@pytest.mark.sandbox
def test_sandbox_has_no_network_key_or_outside_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-non-deve-entrare")
    outside = tmp_path / "riservato.txt"
    outside.write_text("x")
    work = tmp_path / "work"
    work.mkdir()
    box = Sandbox(work)
    # What the sandbox sees, not a failed probe: an offline host also fails to connect, and only root could
    # write to /usr anyway. Only `lo` exists without the host's network, and /usr is mounted read-only.
    probe = (
        "import os,socket;print(os.environ.get('ANTHROPIC_API_KEY'));"
        f"print(os.path.exists({str(outside)!r}));"
        "print(','.join(name for _, name in socket.if_nameindex()));"
        "print(bool(os.statvfs('/usr').f_flag & os.ST_RDONLY))"
    )
    done = box.run(["python3", "-c", probe])
    assert done.stdout.split() == ["None", "False", "lo", "True"]


@pytest.mark.sandbox
@pytest.mark.parametrize("name", API_KEY_VARIABLES)
def test_no_process_in_the_sandbox_holds_the_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    # --clearenv empties only the command's environment. bwrap itself is pid 1 inside the sandbox and keeps
    # the block it was started with, which any sandboxed process can read from /proc/1/environ.
    canary = "sk-ant-canary-in-proc-environ"
    monkeypatch.setenv(name, canary)
    work = tmp_path / "work"
    work.mkdir()
    probe = (
        "import glob\n"
        "read = hits = 0\n"
        "for path in glob.glob('/proc/[0-9]*/environ'):\n"
        "    try:\n"
        "        data = open(path, 'rb').read()\n"
        "    except OSError:\n"
        "        continue\n"
        "    read += 1\n"
        f"    hits += {canary.encode()!r} in data\n"
        "print(open('/proc/1/environ', 'rb').read() != b'', read, hits)"
    )
    done = Sandbox(work).run(["python3", "-c", probe])
    # pid 1's block was read and is not empty, so a zero count is a real absence, not a failed read.
    readable, read, hits = done.stdout.split()
    assert (readable, int(read) >= 2, hits) == ("True", True, "0")


@pytest.mark.sandbox
def test_sandbox_runs_in_a_new_session(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    # With --new-session bwrap calls setsid() before it unshares the pid namespace, so the session leader is
    # the sandbox's own init (pid 1) and the sid is visible inside. Without it the session is the operator's
    # terminal one, outside the namespace, and getsid(0) reads 0: that is what lets TIOCSTI inject keystrokes.
    probe = "import os;print(os.getsid(0))"
    assert Sandbox(work).run(["python3", "-c", probe]).stdout.split() == ["1"]


@pytest.mark.sandbox
def test_sandbox_writes_only_in_its_folder(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    box = Sandbox(work)
    assert box.run(["sh", "-c", f"echo a > {JOB}/ok.txt"]).code == 0
    assert (work / "ok.txt").exists()
    outside = tmp_path / "fuori.txt"
    box.run(["sh", "-c", f"echo a > {outside}; echo a > /etc/agency-probe"])
    assert not outside.exists()
    assert not Path("/etc/agency-probe").exists()


@pytest.mark.sandbox
def test_sandbox_tmp_is_size_limited(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    box = Sandbox(work)
    # The totals come first: a 3G fallocate also fails on the file-size limit alone, so it cannot prove the
    # tmpfs bound, and at an unbounded /tmp it would allocate 3 GiB of RAM.
    probe = (
        "import os;"
        "total=lambda path:(lambda s:s.f_blocks*s.f_frsize)(os.statvfs(path));"
        "print(total('/tmp'), total('/home'))"
    )
    assert box.run(["python3", "-c", probe]).stdout.split() == [str(2 * 2**30), str(256 * 2**20)]
    assert box.run(["fallocate", "-l", "3G", "/tmp/x"]).code != 0


def test_sandbox_file_size_is_limited(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    assert Sandbox(work).run(["truncate", "-s", "3G", f"{JOB}/x"]).code != 0
    assert not (work / "x").exists() or (work / "x").stat().st_size < 3 * 2**30


@pytest.mark.sandbox
def test_sandbox_dev_shm_is_size_limited(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    # `--dev` mounts /dev/shm without a size, so it reports the host's free RAM. The probe writes 1 MiB blocks
    # past the bound and reports why it stopped.
    probe = (
        "import errno,os;s=os.statvfs('/dev/shm');print(s.f_blocks*s.f_frsize);"
        "fd=os.open('/dev/shm/x',os.O_WRONLY|os.O_CREAT);written=0\n"
        f"for _ in range({SHM_BYTES // 2**20 + 1}):\n"
        "    try:\n        written+=os.write(fd,bytes(2**20))\n"
        "    except OSError as exc:\n        print(exc.errno==errno.ENOSPC,written);break\n"
        "else:\n    print('no-error',written)"
    )
    total, enospc, written = Sandbox(work).run(["python3", "-c", probe]).stdout.split()
    assert int(total) <= SHM_BYTES
    assert enospc == "True"
    assert 0 < int(written) <= SHM_BYTES


@pytest.mark.sandbox
def test_sandbox_stops_a_command_that_prints_too_much(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    started = time.monotonic()
    done = Sandbox(work).run(["yes", "ycap"], timeout=60)
    assert time.monotonic() - started < 30
    assert done.code == 125
    assert len(done.stdout) == OUTPUT_BYTES  # all of the cap, never a byte more
    assert done.stdout.startswith("ycap\nycap\n")
    assert done.stderr.endswith(f"\nuscita oltre {OUTPUT_BYTES // 2**20} MiB: comando fermato")
    assert not process_running("yes ycap")


@pytest.mark.sandbox
def test_sandbox_stops_a_command_that_prints_too_much_on_stderr(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    done = Sandbox(work).run(["sh", "-c", "echo before; yes boom >&2"], timeout=60)
    assert done.code == 125
    assert done.stdout == "before\n"
    assert done.stderr.startswith("boom\nboom\n")
    note = f"\nuscita oltre {OUTPUT_BYTES // 2**20} MiB: comando fermato"
    assert len(done.stderr.encode()) == OUTPUT_BYTES + len(note)
    assert not process_running("yes boom")


@pytest.mark.sandbox
def test_sandbox_keeps_exactly_the_cap_of_output(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    done = Sandbox(work).run(["head", "-c", str(OUTPUT_BYTES), "/dev/zero"])
    assert (done.code, len(done.stdout), done.stderr) == (0, OUTPUT_BYTES, "")


@pytest.mark.sandbox
def test_sandbox_stops_a_command_that_prints_one_byte_over_the_cap(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    done = Sandbox(work).run(["head", "-c", str(OUTPUT_BYTES + 1), "/dev/zero"])
    assert (done.code, len(done.stdout)) == (125, OUTPUT_BYTES)


@pytest.mark.sandbox
def test_sandbox_returns_code_and_streams_of_a_normal_command(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    done = Sandbox(work).run(["sh", "-c", "echo out; echo err >&2; printf 'a\\r\\nb\\377'; exit 3"])
    # `text=True` semantics: universal newlines, and a byte that is not UTF-8 is replaced instead of raising.
    assert done == Completed(3, "out\na\nb\ufffd", "err\n")


@pytest.mark.sandbox
def test_a_sandboxed_command_reads_an_empty_closed_stdin(tmp_path: Path) -> None:
    """A command that reads its input gets end of file at once: with stdin left open, `cat` would wait for the
    timeout and answer 124."""
    work = tmp_path / "work"
    work.mkdir()
    assert Sandbox(work).run(["cat"], timeout=10) == Completed(0, "", "")


@pytest.mark.sandbox
def test_sandbox_timeout_returns_124_and_leaves_nothing_running(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    started = time.monotonic()
    done = Sandbox(work).run(["sh", "-c", "sleep 4321.5 & sleep 4321.6"], timeout=2)
    assert time.monotonic() - started < 20
    assert done == Completed(124, "", "tempo scaduto dopo 2 s")
    assert not process_running("sleep 4321")


@pytest.mark.sandbox
def test_sandbox_timeout_also_covers_a_command_that_prints_a_little_and_hangs(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    done = Sandbox(work).run(["sh", "-c", "echo hi; sleep 4322.5"], timeout=2)
    assert done == Completed(124, "", "tempo scaduto dopo 2 s")
    assert not process_running("sleep 4322")


def process_running(marker: str) -> bool:
    """Whether a process whose command line contains `marker` is alive on the host, after a short grace for
    the kernel to reap what was just killed."""
    for _ in range(50):
        found = subprocess.run(["pgrep", "-f", marker], capture_output=True, text=True).stdout.split()
        found = [pid for pid in found if int(pid) != os.getpid()]
        if not found:
            return False
        time.sleep(0.1)
    return True


def host_cgroup(path: str) -> Path:
    return Path("/sys/fs/cgroup") / path.removeprefix("0::/").strip()


@pytest.mark.sandbox
def test_sandbox_runs_in_its_own_capped_scope(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    # The sandbox has no /sys, so the caps are read from the host while the command is still running: it
    # writes its cgroup into /job and waits for a marker. Every wait is bounded, so a failure cannot hang.
    command = (
        f"cat /proc/self/cgroup > {JOB}/cgroup; i=0; "
        f"while [ ! -e {JOB}/done ] && [ $i -lt 300 ]; do sleep 0.1; i=$((i+1)); done"
    )
    results: list[Completed] = []

    def job() -> None:
        results.append(Sandbox(work).run(["sh", "-c", command], timeout=60))

    runner = threading.Thread(target=job)
    runner.start()
    try:
        deadline = time.monotonic() + 30
        while not ((work / "cgroup").exists() and (work / "cgroup").read_text("utf-8")):
            assert time.monotonic() < deadline, "the sandboxed command never reported its cgroup"
            time.sleep(0.1)
        inside = (work / "cgroup").read_text("utf-8").strip()
        scope = host_cgroup(inside)
        assert inside != Path("/proc/self/cgroup").read_text("utf-8").strip()
        assert (scope / "memory.max").read_text("utf-8").strip() == str(MEMORY_MAX_BYTES)
        assert (scope / "memory.swap.max").read_text("utf-8").strip() == "0"
        assert (scope / "pids.max").read_text("utf-8").strip() == str(TASKS_MAX)
    finally:
        (work / "done").write_text("")
        runner.join(timeout=60)
    assert results
    assert results[0].code == 0


def break_the_user_bus(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """`systemd-run --user` cannot reach the user's systemd: the case of a cron job or a bare container."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "no-runtime-dir"))
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)


def test_sandbox_refuses_to_run_without_a_scope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    work = tmp_path / "work"
    work.mkdir()
    break_the_user_bus(monkeypatch, tmp_path)
    with pytest.raises(SandboxUnavailable) as refused:
        Sandbox(work).run(["sh", "-c", f"echo ran > {JOB}/ran"])
    assert "systemd-run" in str(refused.value)  # the reason names what failed
    assert not (work / "ran").exists()  # the command never started, outside any cap


def test_a_missing_scope_reaches_the_model_as_a_tool_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    box = Toolbox(bare_context(tmp_path, "identity-designer"))
    break_the_user_bus(monkeypatch, tmp_path)
    result = box.call("c1", "compute", {"code": "print(1)"})
    assert result["is_error"] is True
    assert "scope" in result["content"]
    assert "Traceback" not in result["content"]
    assert "non è riuscito" not in result["content"]  # a refusal (ADR-0046), not a tool crash
