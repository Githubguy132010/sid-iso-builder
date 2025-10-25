import json
from pathlib import Path

import pytest

from sid_iso_builder.builder import IsoBuildRunner, render_command_sequence
from sid_iso_builder.config import IsoBuildConfig, PackageSelection


def test_render_command_sequence_includes_secure_boot_flag():
    config = IsoBuildConfig(enable_secure_boot=True)
    commands = render_command_sequence(config)
    assert any("--uefi-secure-boot" in cmd for cmd in commands)


def test_render_command_sequence_respects_architecture():
    config = IsoBuildConfig(architecture="arm64")
    commands = render_command_sequence(config)
    assert any("--architectures arm64" in cmd for cmd in commands)
    assert any("live-image-arm64.hybrid.iso" in cmd for cmd in commands)


@pytest.mark.asyncio
async def test_runner_simulation_writes_log(tmp_path: Path):
    config = IsoBuildConfig(workdir=tmp_path, simulate=True)
    runner = IsoBuildRunner(config)
    lines = []

    def collector(line: str) -> None:
        lines.append(line)

    result = await runner.run(callback=collector)
    assert result.success
    assert result.log_path.exists()
    assert lines


def test_export_config(tmp_path: Path):
    config = IsoBuildConfig(workdir=tmp_path, simulate=True, package_selection=PackageSelection.from_csv("curl", ""))
    runner = IsoBuildRunner(config)
    destination = tmp_path / "config.json"
    runner.export_config(destination)
    assert destination.exists()
    data = json.loads(destination.read_text())
    assert data["architecture"] == config.architecture
    assert "package_selection" in data
