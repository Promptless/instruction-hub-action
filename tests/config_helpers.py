"""Explicit ingestion configuration for tests that exercise the managed runtime."""

from pathlib import Path

from promptless_instruction_hub.fs import read_yaml_mapping, write_yaml


def enable_trace_ingestion(hub_root: Path) -> None:
    config_path = hub_root / "hub.yaml"
    config = read_yaml_mapping(config_path)
    config["trace_ingestion"] = {"enabled": True}
    write_yaml(config_path, config)
