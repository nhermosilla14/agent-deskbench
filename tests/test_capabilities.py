"""Capability report: parsing and the install-route message without a container, then the live probe."""

from __future__ import annotations

import json
import unittest

from deskbench import capabilities

from support import ContainerTest, call

DEBIAN_OUTPUT = """\
sh\t/usr/bin/sh
sudo\t/usr/bin/sudo
tmux\t
scrot\t/usr/bin/scrot
import\t
deskbench-capture\t/usr/local/bin/deskbench-capture
apt-get\t/usr/bin/apt-get
dnf\t
zypper\t
apk\t
pacman\t
brew\t
write\tsudo\tyes
"""


def report(managers: dict[str, str] | None = None, possible: bool = True, measured: str = "sudo",
           brew: bool = False) -> dict:
    """A capability report with only the named package managers present."""
    present = {name: f"/usr/bin/{name}" for name in (managers or {})}
    if brew:
        present["brew"] = "/home/linuxbrew/.linuxbrew/bin/brew"
    text = [f"{name}\t{present.get(name, '')}" for name in capabilities.PACKAGE_MANAGERS]
    text.append(f"write\t{measured}\t{'yes' if possible else 'no'}")
    return capabilities.parse_report("\n".join(text) + "\n")


class Report(unittest.TestCase):
    def test_parses_a_debian_like_probe(self):
        parsed = capabilities.parse_report(DEBIAN_OUTPUT)
        self.assertEqual(parsed["shell"], "/usr/bin/sh")
        self.assertEqual(parsed["screenshot"], "/usr/local/bin/deskbench-capture")
        self.assertIsNone(parsed["tmux"])
        self.assertEqual(parsed["package_managers"]["apt-get"], "/usr/bin/apt-get")
        self.assertIsNone(parsed["package_managers"]["brew"])
        self.assertEqual(parsed["privileged_write"], {"possible": True, "measured_with": "sudo"})
        self.assertNotIn("terminal", " ".join(parsed))

    def test_screenshot_falls_back_to_the_first_tool_present(self):
        without_capture = DEBIAN_OUTPUT.replace("/usr/local/bin/deskbench-capture", "")
        parsed = capabilities.parse_report(without_capture)
        self.assertEqual(parsed["screenshot"], "/usr/bin/scrot")

    def test_refuses_output_without_the_write_line(self):
        with self.assertRaises(ValueError):
            capabilities.parse_report("sh\t/usr/bin/sh\n")

    def test_unprivileged_write_is_reported_as_measured(self):
        parsed = capabilities.parse_report(DEBIAN_OUTPUT.replace("write\tsudo\tyes", "write\tuser\tno"))
        self.assertEqual(parsed["privileged_write"], {"possible": False, "measured_with": "user"})


class InstallRoute(unittest.TestCase):
    def test_debian_like_image_is_told_to_use_apt(self):
        message = capabilities.tmux_install_message(
            report({"apt-get": 1}), "flavour 'debian' (image 'debian-image')"
        )
        self.assertIn("apt-get install -y tmux", message)
        self.assertIn("flavour 'debian' (image 'debian-image')", message)
        self.assertIn("capability: tmux", message)
        self.assertNotIn("brew", message)

    def test_alpine_like_image_is_told_to_use_apk_and_never_apt(self):
        message = capabilities.tmux_install_message(report({"apk": 1}), "alpine-image")
        self.assertIn("apk add tmux", message)
        self.assertNotIn("apt-get", message)

    def test_immutable_image_with_brew_is_routed_to_brew_and_never_apt(self):
        message = capabilities.tmux_install_message(
            report({"dnf": 1}, possible=False, measured="user", brew=True), "immutable-image"
        )
        self.assertIn("brew install tmux", message)
        self.assertNotIn("apt-get", message)
        self.assertNotIn("dnf install", message)

    def test_immutable_image_without_brew_says_packages_cannot_be_installed(self):
        message = capabilities.tmux_install_message(
            report({"pacman": 1}, possible=False, measured="user"), "locked-image"
        )
        self.assertIn("cannot install packages the usual way", message)
        self.assertNotIn("apt-get", message)
        self.assertNotIn("pacman -S", message)
        self.assertNotIn("brew install", message)


class Probe(ContainerTest):
    desktop = "e2e-caps"

    def test_capabilities_json_has_the_contracted_keys(self):
        code, out, err = call("capabilities", self.desktop, "--json")
        self.assertEqual(code, 0, err)
        data = json.loads(out)
        self.assertEqual(
            set(data),
            {"shell", "screenshot", "tmux", "sudo", "package_managers", "privileged_write"},
        )
        self.assertTrue(data["tmux"])
        self.assertTrue(data["package_managers"]["apt-get"])
        self.assertEqual(
            set(data["package_managers"]),
            {"apt-get", "dnf", "zypper", "apk", "pacman", "brew"},
        )
        self.assertEqual(data["privileged_write"]["measured_with"], "sudo")
        self.assertTrue(data["privileged_write"]["possible"])

    def test_capabilities_human_output_names_tmux(self):
        code, out, _ = call("capabilities", self.desktop)
        self.assertEqual(code, 0)
        self.assertIn("tmux: /usr/bin/tmux", out)
        self.assertIn("(measured with sudo)", out)
