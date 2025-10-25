"""Command generation and execution helpers for Debian Sid ISO builds."""
from __future__ import annotations

import asyncio
import json
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence

from .config import IsoBuildConfig


def render_command_sequence(config: IsoBuildConfig) -> List[str]:
    """Generate the shell commands required to build the ISO image."""
    components = " ".join(config.components)
    firmware_install = " ".join(config.firmware_packages)
    package_flags = config.package_selection.to_flags()

    chroot_script = textwrap.dedent(
        f"""
        sudo chroot {config.workdir}/chroot /bin/bash -c ""
        apt-get update && \\
        apt-get install -y --no-install-recommends tasksel systemd-sysv && \\
        tasksel install standard && \\
        apt-get install -y linux-image-{config.architecture} live-build squashfs-tools xorriso {firmware_install}
        ""
        """
    ).strip()

    lb_config_parts = [
        "sudo lb config -d sid",
        f"--architectures {config.architecture}",
        "--binary-images iso-hybrid",
        f"--archive-areas '{components}'",
        f"--bootappend-live 'boot=live components quiet username={config.username}'",
    ]
    if config.enable_secure_boot:
        lb_config_parts.append("--uefi-secure-boot on")

    commands: List[str] = [
        f"mkdir -p {config.workdir}/work",
        f"sudo debootstrap --arch={config.architecture} --variant={config.variant} sid {config.workdir}/chroot {config.mirror}",
        f"echo '{config.hostname}' | sudo tee {config.workdir}/chroot/etc/hostname",
        chroot_script,
        " ".join(lb_config_parts),
    ]
    if package_flags:
        commands.append("sudo lb config " + " ".join(package_flags))
    commands.extend(
        [
            "sudo lb build",
            f"sudo cp live-image-{config.architecture}.hybrid.iso {config.workdir}/sid-custom.iso",
        ]
    )
    return [cmd for cmd in commands if cmd]


@dataclass(slots=True)
class BuildResult:
    commands: Sequence[str]
    log_path: Path
    success: bool


class IsoBuildRunner:
    """Execute the build commands sequentially, optionally simulating them."""

    def __init__(self, config: IsoBuildConfig, *, log_dir: Path | None = None) -> None:
        self.config = config
        self.log_dir = log_dir or Path(config.workdir) / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    async def run(self, *, callback) -> BuildResult:
        log_path = self.log_dir / "build.log"
        commands = render_command_sequence(self.config)
        if self.config.simulate:
            await self._simulate(commands, log_path, callback)
            return BuildResult(commands=commands, log_path=log_path, success=True)
        success = await self._execute(commands, log_path, callback)
        return BuildResult(commands=commands, log_path=log_path, success=success)

    async def _simulate(self, commands: Sequence[str], log_path: Path, callback) -> None:
        log_path.write_text("Simulated build run.\n")
        for index, command in enumerate(commands, start=1):
            line = f"[{index}/{len(commands)}] {command}"
            with log_path.open("a", encoding="utf-8") as log_file:
                log_file.write(line + "\n")
            callback(line)
            await asyncio.sleep(0.1)

    async def _execute(self, commands: Sequence[str], log_path: Path, callback) -> bool:
        success = True
        await asyncio.to_thread(log_path.write_text, "")
        for index, command in enumerate(commands, start=1):
            callback(f"[{index}/{len(commands)}] $ {command}")
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            assert process.stdout
            async for line in process.stdout:
                decoded = line.decode().rstrip()
                callback(decoded)
                await asyncio.to_thread(_append_line, log_path, decoded)
            returncode = await process.wait()
            if returncode != 0:
                success = False
                callback(f"Command failed with exit code {returncode}")
                break
        return success

    def export_config(self, destination: Path) -> Path:
        data = self.config.to_dict()
        destination.write_text(json.dumps(data, indent=2))
        return destination


def _append_line(path: Path, line: str) -> None:
    with path.open("a", encoding="utf-8") as log_file:
        log_file.write(line + "\n")
