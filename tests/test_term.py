"""Terminal sessions: grammar without a container, then the verbs end to end through the CLI."""

from __future__ import annotations

import json
import os
import subprocess
import time
import unittest
from unittest import mock

from deskbench import capabilities, engine, flavours, runtime as runtimes, sessions, term

from support import ContainerTest, call

SESSION = "main"


class Grammar(unittest.TestCase):
    def test_accepts_grids_at_the_bounds(self):
        self.assertEqual(term.validate_cells("20x5"), (20, 5))
        self.assertEqual(term.validate_cells("500x200"), (500, 200))
        self.assertEqual(term.validate_cells("120x40"), (120, 40))

    def test_refuses_grids_out_of_bounds(self):
        for value in ("19x40", "501x40", "120x4", "120x201", "0x0", "1x1", "100000x100000"):
            with self.subTest(value=value), self.assertRaises(sessions.SessionError):
                term.validate_cells(value)

    def test_refuses_malformed_grids(self):
        for value in ("", "120", "x40", "120x", "120x40x1", "axb", "120 x 40"):
            with self.subTest(value=value), self.assertRaises(sessions.SessionError):
                term.validate_cells(value)

    def test_parse_list_reads_each_session_grid_and_attached_count(self):
        text = "main\t1\t120\t40\t1\nmain\t1\t80\t24\t0\nother\t0\t80\t24\t1\n"
        listed = term.parse_list(text)
        self.assertEqual(
            [(entry.name, entry.grid, entry.attached) for entry in listed],
            [("main", "120x40", 1), ("other", "80x24", 0)],
        )
        self.assertEqual(listed[0].as_dict(), {"name": "main", "grid": "120x40", "attached": 1})

    def test_parse_list_of_nothing_is_empty(self):
        self.assertEqual(term.parse_list(""), [])

    def test_targets_are_exact_session_names(self):
        self.assertEqual(term.has_session_args("main"), ["has-session", "-t", "=main"])
        self.assertEqual(term.capture_args("main", 0)[-1], "=main:")

    def test_history_adds_scrollback_start_only_when_asked(self):
        self.assertNotIn("-S", term.capture_args("main", 0))
        args = term.capture_args("main", 25)
        self.assertEqual(args[args.index("-S") + 1], "-25")

    def test_text_is_literal_and_cannot_be_read_as_an_option(self):
        self.assertEqual(
            term.send_text_args("main", "-x"),
            ["send-keys", "-t", "=main:", "-l", "--", "-x"],
        )

    def test_ended_message_says_the_session_has_ended(self):
        self.assertIn("has ended", term.ended_message("main", "desk1"))


class StartFailures(unittest.TestCase):
    """Failure paths of ``term start`` that need no tmux-free image, so they are stubbed."""

    NO_TMUX = (
        "apt-get\t/usr/bin/apt-get\n" + "\n".join(
            f"{name}\t" for name in ("sh", "sudo", "tmux", "scrot", "import", "deskbench-capture",
                                      "dnf", "zypper", "apk", "pacman", "brew")
        ) + "\nwrite\tsudo\tyes\n"
    )

    def desktop(self, **labels: str) -> engine.Desktop:
        return engine.Desktop(name="d1", container="deskbench-d1", state="running",
                              url="", id="x", labels=labels)

    def test_missing_tmux_names_the_flavour_and_route_not_a_raw_runtime_error(self):
        report = capabilities.parse_report(self.NO_TMUX)
        desktop = self.desktop(**{sessions.FLAVOUR_LABEL: "debian"})
        with mock.patch.object(engine, "get", return_value=desktop), \
                mock.patch.object(engine, "_capability_report", return_value=report), \
                mock.patch.object(engine, "_image_of", return_value="img:1"), \
                mock.patch.object(engine, "_term_exists",
                                  side_effect=engine.EngineError("exec 127: tmux not found")):
            with self.assertRaises(engine.EngineError) as caught:
                engine.term_start("d1", 80, 24, "main")
        message = str(caught.exception)
        self.assertIn("tmux is missing in flavour 'debian' (image 'img:1')", message)
        self.assertIn("apt-get install -y tmux", message)
        self.assertNotIn("exec 127", message)

    def test_ad_hoc_image_is_named_by_its_image_only(self):
        with mock.patch.object(engine, "_image_of", return_value="img:3"):
            self.assertEqual(
                engine._where(self.desktop(**{sessions.FLAVOUR_LABEL: "image"})),
                "image 'img:3'",
            )

    def test_a_desktop_without_the_flavour_label_names_its_image(self):
        with mock.patch.object(engine, "_image_of", return_value="img:2"):
            self.assertEqual(engine._where(self.desktop()), "image 'img:2'")

    def test_the_flavour_is_recorded_as_a_creation_label(self):
        args = engine._label_args(flavours.get("base"))
        self.assertIn(f"{sessions.FLAVOUR_LABEL}=base", args)

    def test_session_verbs_are_bounded_by_a_timeout(self):
        desktop = self.desktop(**{sessions.RUN_USER_LABEL: "1000"})
        with mock.patch.object(engine, "_podman") as podman:
            engine._tmux(desktop, term.capture_args("main", 0))
        self.assertEqual(podman.call_args.kwargs["timeout"], engine.TERM_TIMEOUT)


class Sessions(ContainerTest):
    """Sessions in one desktop; every test stops the sessions it starts."""

    desktop = "e2e-term"
    size = "1024x768"

    def start(self, session: str = SESSION, cells: str = "80x24") -> None:
        code, _, err = call("term", "start", self.desktop, "--cells", cells, "--session", session)
        self.assertEqual(code, 0, err)
        self.addCleanup(call, "term", "stop", self.desktop, "--session", session)

    def screen(self, session: str = SESSION, *extra: str) -> tuple[int, str, str]:
        return call("term", "screen", self.desktop, "--session", session, *extra)

    def wait_for_screen(self, text: str, session: str = SESSION, timeout: float = 10) -> str:
        deadline = time.monotonic() + timeout
        out = ""
        while time.monotonic() < deadline:
            code, out, _ = self.screen(session)
            if code == 0 and text in out:
                return out
            time.sleep(0.2)
        self.fail(f"{text!r} never appeared on the screen; last screen:\n{out}")

    def listed(self) -> list[dict]:
        code, out, _ = call("term", "list", self.desktop, "--json")
        self.assertEqual(code, 0)
        return json.loads(out)

    def tmux(self, *args: str) -> str:
        """Run tmux directly as the desktop's user, to read what the CLI does not expose."""
        desktop = engine.get(self.desktop)
        user = desktop.labels[sessions.RUN_USER_LABEL]
        binary = runtimes.detect().binary
        proc = subprocess.run(
            [binary, "exec", "--user", user, desktop.container, "tmux", *args],
            capture_output=True, text=True, check=True,
        )
        return proc.stdout.strip()

    def test_echo_is_read_back_through_screen(self):
        self.start()
        code, _, err = call("term", "send", self.desktop, "--session", SESSION, "--", "echo hi")
        self.assertEqual(code, 0, err)
        out = self.wait_for_screen("hi")
        self.assertNotIn("\x1b", out)

    def test_history_shows_a_line_that_scrolled_off(self):
        self.start("hist")
        call("term", "send", self.desktop, "--session", "hist", "--", "seq 1 200")
        self.wait_for_screen("200", "hist")
        _, visible, _ = self.screen("hist")
        _, with_history, _ = self.screen("hist", "--history", "300")
        self.assertNotIn("1", visible.splitlines())
        self.assertIn("1", with_history.splitlines())

    def test_full_screen_program_is_readable_as_a_frame(self):
        self.start("frame")
        call("term", "send", self.desktop, "--session", "frame", "--", "top")
        out = self.wait_for_screen("Tasks:", "frame")
        self.assertIn("PID", out)
        self.assertNotIn("\x1b", out)
        call("term", "send", self.desktop, "--session", "frame", "--key", "q")

    def test_a_prompt_is_answered_through_send(self):
        self.start("prompt")
        call("term", "send", self.desktop, "--session", "prompt", "--", "read answer; echo got=$answer")
        call("term", "send", self.desktop, "--session", "prompt", "--", "42")
        self.wait_for_screen("got=42", "prompt")

    def test_screen_returns_while_a_program_waits_for_input(self):
        self.start("waiting")
        call("term", "send", self.desktop, "--session", "waiting", "--", "read answer")
        started = time.monotonic()
        code, out, err = self.screen("waiting")
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual(code, 0, err)
        self.assertIn("read answer", out)

    def test_exit_ends_the_session_and_screen_and_send_say_so(self):
        self.start("short")
        call("term", "send", self.desktop, "--session", "short", "--", "exit")
        deadline = time.monotonic() + 10
        while any(entry["name"] == "short" for entry in self.listed()):
            if time.monotonic() > deadline:
                self.fail("the session never went away after exit")
            time.sleep(0.2)
        code, _, err = self.screen("short")
        self.assertEqual(code, 1)
        self.assertIn("has ended", err)
        code, _, err = call("term", "send", self.desktop, "--session", "short", "--", "echo late")
        self.assertEqual(code, 1)
        self.assertIn("has ended", err)

    def test_duplicate_session_name_is_refused(self):
        self.start("dupe")
        code, _, err = call("term", "start", self.desktop, "--cells", "80x24", "--session", "dupe")
        self.assertEqual(code, 1)
        self.assertIn("dupe", err)

    def test_unknown_desktop_fails_before_anything_runs(self):
        code, _, err = call("term", "start", "no-such-desktop", "--cells", "80x24")
        self.assertEqual(code, 1)
        self.assertIn("no desktop", err)
        code, _, err = call("term", "list", "no-such-desktop", "--json")
        self.assertEqual(code, 1)
        self.assertIn("no desktop", err)

    def test_list_json_reports_grid_and_attached_count(self):
        self.start("listed", cells="100x30")
        entry = next(item for item in self.listed() if item["name"] == "listed")
        self.assertEqual(entry, {"name": "listed", "grid": "100x30", "attached": 0})

        client = self.attach("listed")
        try:
            deadline = time.monotonic() + 10
            while True:
                entry = next(item for item in self.listed() if item["name"] == "listed")
                if entry["attached"] == 1 or time.monotonic() > deadline:
                    break
                time.sleep(0.2)
            self.assertEqual(entry["attached"], 1)
            self.assertEqual(entry["grid"], "100x30")
        finally:
            self.detach(client)

    def attach(self, session: str) -> tuple[subprocess.Popen, int]:
        """Attach a real client through a pseudo-terminal, as a human's terminal would."""
        desktop = engine.get(self.desktop)
        user = desktop.labels[sessions.RUN_USER_LABEL]
        binary = runtimes.detect().binary
        master, slave = os.openpty()
        client = subprocess.Popen(
            [binary, "exec", "-it", "--user", user, desktop.container,
             "tmux", "attach", "-t", f"={session}"],
            stdin=slave, stdout=slave, stderr=slave, start_new_session=True,
        )
        os.close(slave)
        return client, master

    def detach(self, client: tuple[subprocess.Popen, int]) -> None:
        process, master = client
        process.kill()
        process.wait()
        os.close(master)

    def test_pin_reads_back_as_manual(self):
        self.start("pinned")
        self.assertEqual(self.tmux("show-options", "-w", "-v", "-t", "=pinned:", "window-size"), "manual")

    def test_stop_ends_one_session_and_leaves_the_desktop(self):
        self.start("gone")
        code, _, err = call("term", "stop", self.desktop, "--session", "gone")
        self.assertEqual(code, 0, err)
        self.assertNotIn("gone", [entry["name"] for entry in self.listed()])
        code, out, _ = call("ls", "--json")
        self.assertEqual(code, 0)
        self.assertIn(self.desktop, [entry["name"] for entry in json.loads(out)])
