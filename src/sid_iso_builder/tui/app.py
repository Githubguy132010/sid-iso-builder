"""Textual application providing an interactive Debian Sid ISO builder."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Button, Checkbox, Footer, Header, Input, Label, Select, Static, TextLog

from ..builder import IsoBuildRunner, render_command_sequence
from ..config import IsoBuildConfig, PackageSelection, SUPPORTED_ARCHES, SUPPORTED_VARIANTS


class ConfigUpdated(Message):
    """Dispatched when the configuration changes."""

    def __init__(self, sender, config: IsoBuildConfig) -> None:
        self.config = config
        super().__init__(sender)


class ConfigForm(Static):
    """Left-side configuration form."""

    config: reactive[IsoBuildConfig] = reactive(IsoBuildConfig())

    def __init__(self, config: IsoBuildConfig) -> None:
        super().__init__(id="config-form")
        self.config = config

    def compose(self) -> ComposeResult:
        yield Label("Build configuration", id="form-title")
        yield Select([(arch, arch) for arch in SUPPORTED_ARCHES], value=self.config.architecture, id="architecture")
        yield Select([(variant, variant) for variant in SUPPORTED_VARIANTS], value=self.config.variant, id="variant")
        yield Input(self.config.mirror, placeholder="Mirror URL", id="mirror")
        yield Input(self.config.components_csv(), placeholder="Components (comma separated)", id="components")
        yield Input(self.config.hostname, placeholder="Hostname", id="hostname")
        yield Input(self.config.username, placeholder="Username", id="username")
        yield Input(self.config.firmware_csv(), placeholder="Firmware packages (comma separated)", id="firmware")
        yield Input(
            ", ".join(self.config.package_selection.packages),
            placeholder="Extra packages (comma separated)",
            id="packages",
        )
        yield Input(
            ", ".join(self.config.package_selection.tasks),
            placeholder="Tasksel tasks (comma separated)",
            id="tasks",
        )
        yield Input(str(self.config.workdir), placeholder="Working directory", id="workdir")
        yield Checkbox(label="Simulate build", value=self.config.simulate, id="simulate")
        yield Checkbox(label="Enable Secure Boot support", value=self.config.enable_secure_boot, id="secure_boot")

    def on_select_changed(self, event: Select.Changed) -> None:  # type: ignore[override]
        self._update_config(event.control.id or "", event.value)

    def on_input_changed(self, event: Input.Changed) -> None:  # type: ignore[override]
        field_id = event.control.id or ""
        value = event.value
        if field_id == "components":
            components = [component.strip() for component in value.split(",") if component.strip()]
            self._update_config("components", components)
        elif field_id == "firmware":
            firmware = [pkg.strip() for pkg in value.split(",") if pkg.strip()]
            self._update_config("firmware_packages", firmware)
        elif field_id == "packages":
            package_selection = self.config.package_selection
            package_selection = PackageSelection.from_csv(value, ", ".join(package_selection.tasks))
            self._update_config("package_selection", package_selection)
        elif field_id == "tasks":
            package_selection = self.config.package_selection
            package_selection = PackageSelection.from_csv(
                ", ".join(package_selection.packages), value
            )
            self._update_config("package_selection", package_selection)
        elif field_id == "workdir":
            self._update_config("workdir", Path(value))
        else:
            self._update_config(field_id, value)

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:  # type: ignore[override]
        field_id = event.control.id or ""
        self._update_config(field_id, bool(event.value))

    def _update_config(self, field: str, value) -> None:
        if not field:
            return
        updates = {field: value}
        if field in {"components", "firmware_packages"} and isinstance(value, Iterable):
            updates[field] = list(value)
        if field == "package_selection" and isinstance(value, PackageSelection):
            updates[field] = value
        try:
            self.config = self.config.with_updates(**updates)
        except ValueError:
            self.app.bell()
            return
        self.post_message(ConfigUpdated(self, self.config))


class ScriptPreview(TextLog):
    def __init__(self) -> None:
        super().__init__(id="script-preview", highlight=True)
        self.clear()
        self.write("Command preview will appear here.")

    def update_commands(self, commands: Iterable[str]) -> None:
        self.clear()
        for command in commands:
            self.write(command)


class BuildLog(TextLog):
    def __init__(self) -> None:
        super().__init__(id="build-log", highlight=False)
        self.clear()
        self.write("Build output will appear here.")

    def append_line(self, line: str) -> None:
        self.write(line)
        self.scroll_end(animate=False)

    def reset(self) -> None:
        self.clear()


class IsoBuilderApp(App[None]):
    """Main Textual application."""

    CSS = """
    #body {
        height: 1fr;
    }

    #config-form {
        width: 1fr;
        padding: 1;
        border: solid $surface-lighten-2;
    }

    #config-form Input,
    #config-form Select,
    #config-form Checkbox {
        margin-bottom: 1;
    }

    #right-pane {
        width: 2fr;
        padding: 1;
        border: solid $surface-lighten-2;
    }

    #script-preview,
    #build-log {
        height: 1fr;
        border: round $surface-lighten-1;
        padding: 1;
    }

    #controls {
        height: auto;
        padding-top: 1;
    }

    #form-title {
        text-style: bold;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        Binding("b", "start_build", "Start build", show=True),
        Binding("e", "export_config", "Export config", show=True),
        Binding("r", "reset_form", "Reset", show=True),
    ]

    config = reactive(IsoBuildConfig())

    def compose(self) -> ComposeResult:
        self.script_preview = ScriptPreview()
        self.build_log = BuildLog()
        self.form = ConfigForm(self.config)

        yield Header(show_clock=True)
        with Container(id="body"):
            with Horizontal():
                yield self.form
                with Vertical(id="right-pane"):
                    yield Label("Generated command script", classes="section-title")
                    yield self.script_preview
                    yield Label("Build log", classes="section-title")
                    yield self.build_log
                    with Horizontal(id="controls"):
                        yield Button("Start Build", id="start-build", variant="success")
                        yield Button("Export Config", id="export-config", variant="primary")
                        yield Button("Reset", id="reset", variant="warning")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_preview()

    def on_config_updated(self, message: ConfigUpdated) -> None:
        self.config = message.config
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        commands = render_command_sequence(self.config)
        self.script_preview.update_commands(commands)

    def action_start_build(self) -> None:
        self._start_build()

    def action_export_config(self) -> None:
        self._export_config()

    def action_reset_form(self) -> None:
        self._reset_form()

    def on_button_pressed(self, event: Button.Pressed) -> None:  # type: ignore[override]
        if event.button.id == "start-build":
            self._start_build()
        elif event.button.id == "export-config":
            self._export_config()
        elif event.button.id == "reset":
            self._reset_form()

    def _reset_form(self) -> None:
        self.config = IsoBuildConfig()
        new_form = ConfigForm(self.config)
        self.form.replace(new_form)
        self.form = new_form
        self._refresh_preview()

    def _start_build(self) -> None:
        self.build_log.reset()
        runner = IsoBuildRunner(self.config)

        async def run_build() -> None:
            self.build_log.append_line("Starting build...")
            result = await runner.run(callback=self.build_log.append_line)
            if result.success:
                self.build_log.append_line("Build completed successfully.")
            else:
                self.build_log.append_line("Build failed. Check logs for details.")

        self.run_worker(run_build, exclusive=True, thread=False)

    def _export_config(self) -> None:
        destination = Path(self.config.workdir) / "sid-build-config.json"
        runner = IsoBuildRunner(self.config)
        runner.export_config(destination)
        self.build_log.append_line(f"Configuration exported to {destination}")


def run() -> None:
    app = IsoBuilderApp()
    app.run()


__all__ = ["IsoBuilderApp", "run"]
