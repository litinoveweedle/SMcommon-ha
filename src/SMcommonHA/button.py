"""Buttons shared by Sequent card integrations."""

import inspect
import logging
from functools import partial

from homeassistant.components.button import ButtonEntity
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import generate_entity_id

from . import Card
from .config_support import async_setup_entities
from .const import CONF_CHAN, CONF_STACK, CONF_TYPE

DEFAULT_ICON = "mdi:button-pointer"
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities, card: Card):
    def create(config):
        return Button(
            name=config[CONF_NAME],
            stack=config[CONF_STACK],
            type=config[CONF_TYPE],
            chan=config[CONF_CHAN],
            card=card,
        )

    await async_setup_entities(hass, entry, async_add_entities, "button", create, card)


class Button(ButtonEntity):
    def __init__(self, name, stack, type, chan, card: Card):
        self._card = card
        generated_name = card.domain + str(stack) + "_" + type + "_" + str(chan)
        self._attr_unique_id = generate_entity_id(
            "button.{}", generated_name, current_ids=[]
        )
        self._attr_name = name or generated_name
        self._stack = int(stack)
        self._type = type
        self._chan = int(chan)
        metadata = card.entity_map["button"][type]
        self._attr_icon = metadata.get("icon", {}).get("off", DEFAULT_ICON)

        api = card.api
        if inspect.isclass(api):
            self._SM_set = getattr(card.api(self._stack), metadata["com"]["set"])
        else:
            self._SM_set = partial(getattr(api, metadata["com"]["set"]), self._stack)
        self._has_channel = bool(inspect.signature(self._SM_set).parameters)

    def press(self, **kwargs):
        try:
            if self._has_channel:
                self._SM_set(self._chan)
            else:
                self._SM_set()
        except Exception as ex:
            _LOGGER.error("%s %s press failed, %s", self._card.domain, self._type, ex)
