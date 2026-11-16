"""Select entities for Sequent card integrations."""

import inspect
import logging
import time
from functools import partial

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import generate_entity_id

from . import Card
from .config_support import async_setup_entities
from .const import CONF_CHAN, CONF_NAME, CONF_STACK, CONF_TYPE

_LOGGER = logging.getLogger(__name__)
DEFAULT_ICON = "mdi:format-list-bulleted"


async def async_setup_entry(hass, entry, async_add_entities, card: Card):
    def create(config):
        return Select(
            name=config[CONF_NAME],
            stack=config[CONF_STACK],
            type=config[CONF_TYPE],
            chan=config[CONF_CHAN],
            card=card,
        )

    await async_setup_entities(hass, entry, async_add_entities, "select", create, card)


class Select(SelectEntity):
    """A card setting represented by a choice of named options."""

    def __init__(self, name, stack, type, chan, card: Card):
        self._card = card
        self._stack = int(stack)
        self._type = type
        self._chan = int(chan)
        generated_name = card.domain + str(stack) + "_" + type + "_" + str(chan)
        self._attr_unique_id = generate_entity_id(
            "select.{}", generated_name, current_ids=[]
        )
        self._attr_name = name or generated_name
        metadata = card.entity_map["select"][type]
        self._attr_icon = metadata.get("icon", {}).get("off", DEFAULT_ICON)
        self._option_map = dict(metadata["option_map"])
        if not self._option_map or any(
            not isinstance(option, str) or not option for option in self._option_map
        ):
            raise ValueError(f"Select {type} must have non-empty string options")
        self._reverse_options = {
            value: option for option, value in self._option_map.items()
        }
        if len(self._reverse_options) != len(self._option_map):
            raise ValueError(f"Select {type} has duplicate option values")
        self._attr_options = list(self._option_map)
        self._attr_current_option = None

        api = card.api
        if inspect.isclass(api):
            api = api(self._stack)
            self._get = getattr(api, metadata["com"]["get"])
            self._set = getattr(api, metadata["com"]["set"])
        else:
            self._get = partial(getattr(api, metadata["com"]["get"]), self._stack)
            self._set = partial(getattr(api, metadata["com"]["set"]), self._stack)
        self._get_uses_channel = bool(inspect.signature(self._get).parameters)
        self._set_uses_channel = len(inspect.signature(self._set).parameters) > 1

    def update(self):
        time.sleep(0.05)
        try:
            value = self._get(self._chan) if self._get_uses_channel else self._get()
        except OSError as err:
            _LOGGER.error(
                "%s %s read failed for stack %s channel %s: %s",
                self._card.domain,
                self._type,
                self._stack,
                self._chan,
                err,
            )
            self._attr_current_option = None
            return
        try:
            self._attr_current_option = self._reverse_options[value]
        except (KeyError, TypeError):
            _LOGGER.error(
                "%s %s invalid reading %r for stack %s channel %s",
                self._card.domain,
                self._type,
                value,
                self._stack,
                self._chan,
            )
            self._attr_current_option = None

    def select_option(self, option: str) -> None:
        if option not in self._option_map:
            raise ValueError(f"Invalid option {option!r} for {self._type}")
        value = self._option_map[option]
        if self._set_uses_channel:
            self._set(self._chan, value)
        else:
            self._set(value)
        self._attr_current_option = option
