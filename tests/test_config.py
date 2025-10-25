from pathlib import Path

import pytest

from sid_iso_builder.config import IsoBuildConfig, PackageSelection


def test_package_selection_from_csv():
    selection = PackageSelection.from_csv("curl, git", "standard, desktop")
    assert selection.packages == ["curl", "git"]
    assert selection.tasks == ["standard", "desktop"]


def test_config_validation_rejects_unknown_arch():
    with pytest.raises(ValueError):
        IsoBuildConfig(architecture="mipsel")


def test_config_with_updates_changes_fields():
    config = IsoBuildConfig()
    updated = config.with_updates(mirror="http://mirror", hostname="testhost")
    assert updated.mirror == "http://mirror"
    assert updated.hostname == "testhost"
    assert updated.architecture == config.architecture


def test_config_to_from_dict_roundtrip(tmp_path: Path):
    config = IsoBuildConfig(workdir=tmp_path)
    data = config.to_dict()
    restored = IsoBuildConfig.from_dict(data)
    assert restored == config
