DEFAULT_ICONS = {
    "on": "mdi:toggle-switch-variant",
    "off": "mdi:toggle-switch-variant-off",
}

import inspect
import logging
import time
import types
from inspect import signature

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import generate_entity_id

from . import Card
from .config_support import async_setup_entities
from .const import CONF_CHAN, CONF_STACK, CONF_TYPE

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities, card: Card):
    def create(config):
        return Switch(
            name=config[CONF_NAME],
            stack=config[CONF_STACK],
            type=config[CONF_TYPE],
            chan=config[CONF_CHAN],
            hass=hass,
            card=card,
        )

    await async_setup_entities(hass, entry, async_add_entities, "switch", create, card)


class Switch(SwitchEntity):
    def __init__(self, name, stack, type, chan, hass, card: Card):
        self._card = card
        sm_map = card.entity_map["switch"]
        generated_name = card.domain + str(stack) + "_" + type + "_" + str(chan)
        self._attr_unique_id = generate_entity_id(
            "switch.{}", generated_name, current_ids=[]
        )
        self._attr_name = name or generated_name
        self._stack = int(stack)
        self._type = type
        self._chan = int(chan)
        self._short_timeout = 0.05
        self._icons = DEFAULT_ICONS | sm_map[self._type].get("icon", {})
        self._attr_icon = self._icons["off"]
        self.__SM__init()
        self._attr_is_on = self._SM_get(self._chan)
        ### __CUSTOM_SETUP__ START
        ### __CUSTOM_SETUP__ END

    def __SM__init(self):
        com = self._card.entity_map["switch"][self._type]["com"]
        self._SM = self._card.api
        if inspect.isclass(self._SM):
            self._SM = self._card.api(self._stack)
            self._SM_get = getattr(self._SM, com["get"])
            self._SM_set = getattr(self._SM, com["set"])
            if len(signature(self._SM_get).parameters) == 0:

                def _aux2_SM_get(self, _):
                    return getattr(self, com["get"])()

                self._SM_get = types.MethodType(_aux2_SM_get, self._SM)
            if len(signature(self._SM_set).parameters) == 1:

                def _aux2_SM_set(self, _, value):
                    getattr(self, com["set"])(value)

                self._SM_set = types.MethodType(_aux2_SM_set, self._SM)
        else:
            _SM_get = getattr(self._SM, com["get"])
            if len(signature(_SM_get).parameters) == 1:

                def _aux3_SM_get(_, *args):
                    return _SM_get(self._stack, *args)

                self._SM_get = _aux3_SM_get
            else:

                def _aux_SM_get(*args):
                    return _SM_get(self._stack, *args)

                self._SM_get = _aux_SM_get
            _SM_set = getattr(self._SM, com["set"])
            if len(signature(_SM_set).parameters) == 2:

                def _aux3_SM_set(_, *args):
                    return _SM_set(self._stack, *args)

                self._SM_set = _aux3_SM_set
            else:

                def _aux_SM_set(*args):
                    return _SM_set(self._stack, *args)

                self._SM_set = _aux_SM_set

    def update(self):
        time.sleep(self._short_timeout)
        try:
            self._attr_is_on = self._SM_get(self._chan)
        except Exception as ex:
            _LOGGER.error(
                self._card.domain + " %s update() failed, %s, %s, %s",
                self._type,
                ex,
                str(self._stack),
                str(self._chan),
            )
            return
        if self._attr_is_on:
            self._attr_icon = self._icons["on"]
        else:
            self._attr_icon = self._icons["off"]

    def turn_on(self, **kwargs):
        try:
            self._SM_set(self._chan, 1)
        except Exception as ex:
            _LOGGER.error(self._card.domain + " %s turn ON failed, %s", self._type, ex)

    def turn_off(self, **kwargs):
        try:
            self._SM_set(self._chan, 0)
        except Exception as ex:
            _LOGGER.error(self._card.domain + " %s turn OFF failed, %s", self._type, ex)
