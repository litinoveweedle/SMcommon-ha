"""Shared Home Assistant setup and YAML migration."""

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir

from . import Card
from .config_support import entry_entities, import_yaml_card
from .const import CONF_STACK

_LOGGER = logging.getLogger(__name__)


def config_schema(card: Card):
    """Allow legacy YAML to be imported once."""
    return vol.Schema(
        {
            vol.Optional(card.domain): vol.Schema(
                vol.Any(
                    None,
                    [
                        vol.Schema(
                            {
                                vol.Optional(CONF_STACK, default="0"): cv.string,
                            },
                            extra=vol.ALLOW_EXTRA,
                        )
                    ],
                    {},
                )
            )
        },
        extra=vol.ALLOW_EXTRA,
    )


async def async_setup(hass, config, card: Card):
    """Migrate legacy registry entries and import YAML configuration."""
    registry = er.async_get(hass)
    legacy_entities = [
        entry
        for entry in registry.entities.values()
        if entry.platform == card.legacy_domain
    ]
    for entry in legacy_entities:
        if registry.async_get_entity_id(entry.domain, card.domain, entry.unique_id):
            raise RuntimeError(
                f"Cannot migrate {entry.entity_id}: its unique ID already exists "
                f"under {card.domain}"
            )
    for entry in legacy_entities:
        registry.async_update_entity_platform(entry.entity_id, card.domain)

    if card.domain not in config:
        ir.async_delete_issue(hass, card.domain, "remove_yaml")
        return True
    ir.async_create_issue(
        hass,
        card.domain,
        "remove_yaml",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="remove_yaml",
    )
    for config_card in config[card.domain] or [{}]:
        try:
            imported = import_yaml_card(card, config_card)
            if not 0 <= imported[CONF_STACK] <= 7:
                raise ValueError("stack must be between 0 and 7")
        except (TypeError, ValueError) as err:
            _LOGGER.error(
                "Cannot import %s YAML card configuration: %s", card.domain, err
            )
            continue
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                card.domain,
                context={"source": config_entries.SOURCE_IMPORT},
                data=imported,
            )
        )
    return True


async def async_setup_entry(hass, entry, card: Card):
    """Set up a card from a config entry."""
    entry.runtime_data = entry_entities(card, entry)
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(card.domain, str(entry.data[CONF_STACK]))},
        manufacturer="Sequent Microsystems",
        model=card.full_name,
        name=f"{card.full_name} - stack {entry.data[CONF_STACK]}",
    )
    await hass.config_entries.async_forward_entry_setups(entry, list(card.entity_map))
    return True


async def async_unload_entry(hass, entry, card: Card):
    """Unload the card and its platforms."""
    return await hass.config_entries.async_unload_platforms(
        entry, list(card.entity_map)
    )
