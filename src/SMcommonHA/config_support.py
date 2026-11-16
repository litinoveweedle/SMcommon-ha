"""Configuration helpers shared by the Sequent card integrations."""

import logging
import math

from homeassistant.exceptions import ConfigEntryError, PlatformNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import generate_entity_id

from . import Card
from .const import (
    CONF_CHAN,
    CONF_CHAN_RANGE,
    CONF_CHANNELS,
    CONF_ENTITIES,
    CONF_INTERVALS,
    CONF_NAME,
    CONF_STACK,
    CONF_TYPE,
    CONF_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


def available_entities(card: Card, stack):
    """Return all entities supported by a card, indexed by type and channel."""
    entities = {}
    for platform, types in card.entity_map.items():
        for entity_type, metadata in types.items():
            for channel in range(1, int(metadata["chan_no"]) + 1):
                key = f"{entity_type}_{channel}"
                if key in entities:
                    raise ValueError(f"Duplicate entity configuration key: {key}")
                entities[key] = {
                    CONF_NAME: f"{card.name_prefix}{stack}_{key}",
                    CONF_STACK: stack,
                    CONF_TYPE: entity_type,
                    CONF_CHAN: channel,
                    "platform": platform,
                    "optional": metadata.get("optional", False),
                }
    return entities


def import_yaml_card(card: Card, config):
    """Convert one legacy YAML card into a config-entry configuration."""
    stack = int(config.get(CONF_STACK, 0))
    available = available_entities(card, stack)
    configured = {key: value for key, value in config.items() if key != CONF_STACK}
    if not configured:
        selected = {
            key: entity for key, entity in available.items() if not entity["optional"]
        }
    else:
        selected = {}
        for name, options in configured.items():
            options = options or {}
            try:
                channels = options.get(CONF_CHANNELS)
                channel_range = options.get(CONF_CHAN_RANGE)
                if channels is not None:
                    if not isinstance(channels, str):
                        raise ValueError("channels must be a comma-separated string")
                    channel_numbers = [int(channel) for channel in channels.split(",")]
                    if len(channel_numbers) != len(set(channel_numbers)):
                        raise ValueError("duplicate channels")
                    entity_type = name
                elif channel_range is not None:
                    if not isinstance(channel_range, str):
                        raise ValueError("chan_range must be a start..end string")
                    start, end = (int(channel) for channel in channel_range.split(".."))
                    if end < start:
                        raise ValueError("end must not be less than start")
                    channel_numbers = range(start, end + 1)
                    entity_type = name
                else:
                    entity_type, channel = name.rsplit("_", 1)
                    channel_numbers = [int(channel)]
                interval = options.get(CONF_UPDATE_INTERVAL)
                if interval is not None and (
                    not math.isfinite(float(interval)) or float(interval) <= 0
                ):
                    raise ValueError("update_interval must be finite and positive")
                keys = [f"{entity_type}_{channel}" for channel in channel_numbers]
                if any(key not in available for key in keys):
                    raise ValueError("unknown entity type or channel")
            except (AttributeError, TypeError, ValueError) as err:
                _LOGGER.error("Invalid YAML entity %s: %s", name, err)
                continue
            for key in keys:
                entity = available[key].copy()
                if interval is not None:
                    entity[CONF_UPDATE_INTERVAL] = float(interval)
                selected[key] = entity
    return {CONF_STACK: stack, CONF_ENTITIES: selected}


def entry_entities(card: Card, entry):
    """Return selected entities, preserving imported settings and applying options."""
    available = available_entities(card, entry.data[CONF_STACK])
    imported = entry.data[CONF_ENTITIES]
    selected = entry.options.get(CONF_ENTITIES, list(imported))
    intervals = entry.options.get(CONF_INTERVALS, {})
    entities = []
    for key in selected:
        entity = {**available[key], **imported.get(key, {})}
        if key in intervals:
            entity[CONF_UPDATE_INTERVAL] = intervals[key]
        entities.append(entity)
    return entities


async def async_setup_entities(
    hass, entry, async_add_entities, platform, factory, card: Card
):
    """Create one platform's entities without blocking the event loop."""
    configs = [item for item in entry.runtime_data if item["platform"] == platform]
    registry = er.async_get(hass)
    entities = []
    for config in configs:
        base_id = generate_entity_id(
            f"{platform}.{{}}",
            f"{card.domain}{config[CONF_STACK]}_{config[CONF_TYPE]}_{config[CONF_CHAN]}",
            current_ids=[],
        )
        unique_id = base_id
        if not registry.async_get_entity_id(platform, card.domain, base_id):
            matches = [
                item.unique_id
                for item in registry.entities.values()
                if item.domain == platform
                and item.platform == card.domain
                and item.config_entry_id in (None, entry.entry_id)
                and item.original_name == config[CONF_NAME]
                and item.unique_id.startswith(base_id + "_")
                and item.unique_id[len(base_id) + 1 :].isdigit()
            ]
            if len(matches) > 1:
                raise ConfigEntryError(
                    f"Ambiguous legacy entity for {config[CONF_NAME]}"
                )
            if matches:
                unique_id = matches[0]
        try:
            entity = await hass.async_add_executor_job(factory, config)
        except OSError as err:
            raise PlatformNotReady(
                f"Cannot initialize {config[CONF_NAME]}: {err}"
            ) from err
        entity._unique_id = unique_id
        entity._attr_unique_id = unique_id
        entity._attr_device_info = {
            "identifiers": {(entry.domain, str(config[CONF_STACK]))},
            "manufacturer": "Sequent Microsystems",
            "model": card.full_name,
        }
        entities.append(entity)
    async_add_entities(entities)
