"""Typed models for Instruction Hub source and generated manifests."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Harness = Literal["claude", "codex", "gemini", "cursor"]
AssetKind = Literal["skill", "rule", "agent", "command", "hook", "mcp"]
SupportMode = Literal["agent-skill", "native", "projected", "unsupported"]

SUPPORTED_HARNESSES: tuple[Harness, ...] = ("claude", "codex", "gemini", "cursor")
ASSET_KINDS: tuple[AssetKind, ...] = ("skill", "rule", "agent", "command", "hook", "mcp")
PIG_PLUGIN_ID = "pig"
PIG_PLUGIN_NAME = "PIG"
UPDATE_INSTRUCTION_HUB_SKILL_ID = "update-instruction-hub"
IDENTIFIER_PATTERN = r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$"
IDENTIFIER_RE = re.compile(IDENTIFIER_PATTERN)
SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|[0-9A-Za-z-]*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


def validate_identifier(value: str, field_name: str) -> str:
    """Validate a kebab-case identifier used in generated file paths."""

    if IDENTIFIER_RE.match(value) is None:
        msg = f"{field_name} must be a kebab-case identifier"
        raise ValueError(msg)
    return value


def validate_asset_ref(value: str) -> str:
    """Validate an asset reference in `kind:id` form."""

    kind, separator, asset_id = value.partition(":")
    if separator != ":":
        msg = "plugin includes must use kind:id asset references"
        raise ValueError(msg)
    if kind not in ASSET_KINDS:
        msg = f"unknown asset kind in reference: {kind}"
        raise ValueError(msg)
    validate_identifier(asset_id, "asset reference id")
    return value


class TargetSupport(BaseModel):
    """Declared delivery behavior for one asset on one harness."""

    model_config = ConfigDict(extra="forbid")

    mode: SupportMode
    reason: str | None = None

    @model_validator(mode="after")
    def require_reason_for_unsupported(self) -> "TargetSupport":
        """Require an explicit explanation when an asset is not distributed."""

        if self.mode == "unsupported" and not self.reason:
            msg = "unsupported target support requires a reason"
            raise ValueError(msg)
        return self


class MarketplaceDefinition(BaseModel):
    """Literal marketplace identity shared by every target."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str = Field(min_length=1)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        """Ensure marketplace IDs are stable kebab-case identifiers."""

        return validate_identifier(value, "marketplace.id")


class HubConfig(BaseModel):
    """Root `hub.yaml` configuration."""

    model_config = ConfigDict(extra="forbid")

    org: str = Field(min_length=1)
    marketplace: MarketplaceDefinition
    plugin_version: str
    stable_plugins: list[str] = Field(default_factory=lambda: [PIG_PLUGIN_ID], min_length=1)
    targets: list[Harness] = Field(default_factory=lambda: list(SUPPORTED_HARNESSES), min_length=1)

    @field_validator("plugin_version")
    @classmethod
    def validate_plugin_version(cls, value: str) -> str:
        """Require SemVer for native plugin versions."""

        if SEMVER_RE.match(value) is None:
            msg = "plugin_version must be SemVer, for example 1.2.3"
            raise ValueError(msg)
        return value

    @field_validator("stable_plugins")
    @classmethod
    def validate_stable_plugins(cls, value: list[str]) -> list[str]:
        """Ensure stable plugin references are valid plugin IDs."""

        _validate_unique(value, "stable_plugins")
        plugin_ids = [validate_identifier(plugin_id, "stable plugin id") for plugin_id in value]
        if PIG_PLUGIN_ID not in plugin_ids:
            msg = f"stable_plugins must include the required {PIG_PLUGIN_ID!r} plugin"
            raise ValueError(msg)
        return plugin_ids

    @field_validator("targets")
    @classmethod
    def validate_targets(cls, value: list[Harness]) -> list[Harness]:
        """Ensure target lists do not contain duplicate harnesses."""

        _validate_unique(value, "targets")
        return value


class PluginDefinition(BaseModel):
    """Product-facing plugin grouping for governed assets."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str = Field(min_length=1)
    owners: list[str] = Field(default_factory=list)
    includes: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        """Ensure plugin IDs are stable kebab-case identifiers."""

        return validate_identifier(value, "plugin id")

    @field_validator("includes")
    @classmethod
    def validate_includes(cls, value: list[str]) -> list[str]:
        """Ensure plugin includes are structured asset references."""

        _validate_unique(value, "plugin includes")
        return [validate_asset_ref(asset_ref) for asset_ref in value]


class AssetMetadata(BaseModel):
    """Optional per-asset metadata stored next to source content."""

    model_config = ConfigDict(extra="forbid")

    id: str
    type: AssetKind
    title: str | None = None
    source_path: str | None = None
    support: dict[Harness, TargetSupport] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        """Ensure asset IDs are safe generated path segments."""

        return validate_identifier(value, "asset id")


class LoadedAsset(BaseModel):
    """Resolved asset with source path, metadata, and content hash."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    id: str
    type: AssetKind
    path: Path
    metadata: AssetMetadata
    content_hash: str

    @property
    def ref(self) -> str:
        """Return the `kind:id` reference for this asset."""

        return f"{self.type}:{self.id}"

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        """Ensure loaded asset IDs remain safe path segments."""

        return validate_identifier(value, "asset id")


@dataclass(frozen=True)
class StablePlugin:
    """Resolved stable plugin and the assets to render into its plugin payload."""

    definition: PluginDefinition
    assets: tuple[LoadedAsset, ...]


def _validate_unique(values: Sequence[str], field_name: str) -> None:
    if len(set(values)) == len(values):
        return
    msg = f"{field_name} must not contain duplicates"
    raise ValueError(msg)
