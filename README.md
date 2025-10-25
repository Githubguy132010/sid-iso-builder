# sid-iso-builder

An interactive Textual-based terminal user interface (TUI) that guides you through configuring and orchestrating the build of a Debian Sid ISO image.

## Features

- Guided configuration of architecture, firmware, mirrors, and package selections
- Live preview of the generated build script
- Streaming build log view with simulated or real execution
- Export configuration to JSON for automation

## Usage

```bash
pip install -e .
sid-iso-builder
```

Within the interface use the left-hand form to adjust options and press **b** or the *Start Build* button to launch the build orchestration.  The right column shows the generated script and build log.

To perform a dry run without executing shell commands, toggle *Simulate build*.

## Development

Install development dependencies and run the test suite:

```bash
pip install -e .[dev]
pytest
```
