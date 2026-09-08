"""Shared helpers for target plugin renderers."""

from __future__ import annotations

from pathlib import Path

from promptless_instruction_hub.fs import JsonValue
from promptless_instruction_hub.models import PIG_PLUGIN_ID, HubConfig, PluginDefinition

RenderedAssets = dict[str, list[str]]


def base_plugin_manifest(config: HubConfig, plugin: PluginDefinition) -> dict[str, JsonValue]:
    """Return manifest fields shared by all generated target plugins."""

    return {
        "name": plugin.id,
        "version": config.plugin_version,
        "description": plugin_description(config, plugin),
    }


def plugin_description(config: HubConfig, plugin: PluginDefinition) -> str:
    """Return the stable user-facing plugin description."""

    if plugin.id == PIG_PLUGIN_ID:
        if not config.trace_ingestion.enabled:
            return f"Instruction Hub guidance and updates for {config.org}."
        return f"Promptless Instruction Governance instructions and lifecycle integration for {config.org}."
    return f"Governed agent instructions for {config.org}: {plugin.name}."


def manifest_key_for(asset_type: str) -> str:
    """Return the generated manifest collection key for an asset type."""

    if asset_type == "rule":
        return "rules"
    return f"{asset_type}s"


def directory_for(asset_type: str) -> Path:
    """Return the generated native asset directory for an asset type."""

    return Path(manifest_key_for(asset_type))
