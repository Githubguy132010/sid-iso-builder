"""Configuration models for Debian Sid ISO builds."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Iterable, List


SUPPORTED_ARCHES = [
    "amd64",
    "arm64",
    "armhf",
    "i386",
    "ppc64el",
    "s390x",
]

SUPPORTED_VARIANTS = ["minbase", "standard", "buildd"]


@dataclass(slots=True)
class PackageSelection:
    """Represents packages and tasks to install into the ISO image."""

    packages: List[str] = field(default_factory=list)
    tasks: List[str] = field(default_factory=list)

    @classmethod
    def from_csv(cls, package_csv: str = "", task_csv: str = "") -> "PackageSelection":
        """Create from comma separated strings."""
        packages = [pkg.strip() for pkg in package_csv.split(",") if pkg.strip()]
        tasks = [task.strip() for task in task_csv.split(",") if task.strip()]
        return cls(packages=packages, tasks=tasks)

    def to_flags(self) -> List[str]:
        """Render the selection as debootstrap tasksel flags."""
        flags: List[str] = []
        if self.packages:
            flags.append(f"--include={' '.join(self.packages)}")
        if self.tasks:
            flags.extend(f"--tasksel={task}" for task in self.tasks)
        return flags


@dataclass(slots=True)
class IsoBuildConfig:
    """In-memory representation of a Debian Sid ISO build configuration."""

    architecture: str = "amd64"
    mirror: str = "http://deb.debian.org/debian"
    components: List[str] = field(default_factory=lambda: ["main", "contrib", "non-free-firmware"])
    variant: str = "standard"
    hostname: str = "sid-builder"
    username: str = "sid"
    enable_secure_boot: bool = True
    firmware_packages: List[str] = field(default_factory=lambda: ["firmware-linux"])
    package_selection: PackageSelection = field(default_factory=PackageSelection)
    workdir: Path = Path("./sid-build")
    simulate: bool = True

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Validate configuration values raising ``ValueError`` when invalid."""
        if self.architecture not in SUPPORTED_ARCHES:
            raise ValueError(f"Unsupported architecture: {self.architecture}")
        if self.variant not in SUPPORTED_VARIANTS:
            raise ValueError(f"Unsupported variant: {self.variant}")
        if not self.components:
            raise ValueError("At least one repository component must be selected")
        if not self.mirror:
            raise ValueError("A Debian mirror must be provided")
        if not self.hostname:
            raise ValueError("Hostname cannot be empty")
        if not self.username:
            raise ValueError("Username cannot be empty")

    def components_csv(self) -> str:
        return ", ".join(self.components)

    def firmware_csv(self) -> str:
        return ", ".join(self.firmware_packages)

    def to_dict(self) -> Dict[str, object]:
        data = asdict(self)
        data["workdir"] = str(self.workdir)
        return data

    def with_updates(self, **updates: object) -> "IsoBuildConfig":
        fields = self.to_dict()
        fields.update(updates)
        package_selection = fields.get("package_selection")
        if isinstance(package_selection, dict):
            fields["package_selection"] = PackageSelection(**package_selection)
        workdir = fields.get("workdir")
        if isinstance(workdir, str):
            fields["workdir"] = Path(workdir)
        return IsoBuildConfig(**fields)

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "IsoBuildConfig":
        package_selection = data.get("package_selection", {})
        if isinstance(package_selection, dict):
            data = {**data, "package_selection": PackageSelection(**package_selection)}
        workdir = data.get("workdir")
        if isinstance(workdir, str):
            data = {**data, "workdir": Path(workdir)}
        return cls(**data)

    def update_lists(
        self, *, components: Iterable[str] | None = None, firmware_packages: Iterable[str] | None = None
    ) -> "IsoBuildConfig":
        return IsoBuildConfig(
            architecture=self.architecture,
            mirror=self.mirror,
            components=list(components or self.components),
            variant=self.variant,
            hostname=self.hostname,
            username=self.username,
            enable_secure_boot=self.enable_secure_boot,
            firmware_packages=list(firmware_packages or self.firmware_packages),
            package_selection=self.package_selection,
            workdir=self.workdir,
            simulate=self.simulate,
        )
