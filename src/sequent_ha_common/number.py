DEFAULT_ICONS = {
        "on": "mdi:numeric",
        "off": "mdi:numeric-0",
}

import inspect
import logging
import time
import types
from inspect import signature

_LOGGER = logging.getLogger(__name__)

from homeassistant.components.number import NumberEntity
from homeassistant.helpers.entity import generate_entity_id

from . import Card
from .const import (
    COM_NOGET,
    CONF_CHAN,
    CONF_NAME,
    CONF_STACK,
    CONF_TYPE,
)
from .config_support import async_setup_entities

async def async_setup_entry(hass, entry, async_add_entities, card: Card):
    def create(config):
        entity_class = Number_NOGET if card.entity_map["number"][config[CONF_TYPE]]["com"]["get"] == COM_NOGET else Number
        return entity_class(
            hass=hass, name=config[CONF_NAME], stack=config[CONF_STACK],
            type=config[CONF_TYPE], chan=config[CONF_CHAN], card=card,
        )
    await async_setup_entities(hass, entry, async_add_entities, "number", create, card)

class Number(NumberEntity):
    def __init__(self, hass, name, stack, type, chan, card: Card):
        self._card = card
        sm_map = card.entity_map["number"]
        generated_name = card.domain + str(stack) + "_" + type + "_" + str(chan)
        self._attr_unique_id = generate_entity_id("number.{}", generated_name, current_ids=[])
        self._attr_name = name or generated_name
        self._stack = int(stack)
        self._type = type
        self._chan = int(chan)
        self._short_timeout = .05
        self._icons = DEFAULT_ICONS | sm_map[self._type].get("icon", {})
        self._attr_icon = self._icons["off"]
        self._attr_native_unit_of_measurement = sm_map[self._type].get("uom", "")
        min_value = sm_map[self._type]["min_value"]
        step = sm_map[self._type]["step"]
        if not isinstance(min_value, (int, float)) or not isinstance(step, (int, float)):
            raise TypeError(f"Invalid numeric metadata for {self._type}")
        self._min_value = min_value
        self._max_value = sm_map[self._type]["max_value"]
        self._step = step
        self._attr_native_min_value = self._min_value
        self._attr_native_max_value = self._max_value
        self._attr_native_step = self._step
        self._attr_native_value = 0
        self._sm_init()
        ### __CUSTOM_SETUP__ START
        ### __CUSTOM_SETUP__ END

    def _sm_init(self):
        com = self._card.entity_map["number"][self._type]["com"]
        self._SM = self._card.api
        if inspect.isclass(self._SM):
            self._SM = self._card.api(self._stack)
            self._SM_get = getattr(self._SM, com["get"])
            self._SM_set = getattr(self._SM, com["set"])
            if len(signature(self._SM_get).parameters) == 0:
                def _aux2_SM_get(self, _):
                    return getattr(self, com["get"])()
                self._SM_get = types.MethodType(_aux2_SM_get, self._SM)
            if self._step == int(self._step) and self._min_value == int(self._min_value):
                if len(signature(self._SM_set).parameters) == 1:
                    def _aux2_SM_set(self, _, value):
                        getattr(self, com["set"])(int(value))
                    self._SM_set = types.MethodType(_aux2_SM_set, self._SM)
            else:
                if len(signature(self._SM_set).parameters) == 1:
                    def _aux2_SM_set(self, _, value):
                        getattr(self, com["set"])(value)
                    self._SM_set = types.MethodType(_aux2_SM_set, self._SM)
        else:
            _SM_get = getattr(self._SM, com["get"])
            if len(signature(_SM_get).parameters) == 1:
                def _aux3_SM_get(_):
                    return _SM_get(self._stack)
                self._SM_get = _aux3_SM_get
            else:
                def _aux_SM_get(chan):
                    return _SM_get(self._stack, chan)
                self._SM_get = _aux_SM_get
            _SM_set = getattr(self._SM, com["set"])
            if self._step == int(self._step) and self._min_value == int(self._min_value):
                if len(signature(_SM_set).parameters) == 2:
                    def _aux3_SM_set(_, value):
                        return _SM_set(self._stack, int(value))
                    self._SM_set = _aux3_SM_set
                else:
                    def _aux_SM_set(chan, value):
                        return _SM_set(self._stack, chan, int(value))
                    self._SM_set = _aux_SM_set
            else:
                if len(signature(_SM_set).parameters) == 2:
                    def _aux3_SM_set(_, value):
                        return _SM_set(self._stack, value)
                    self._SM_set = _aux3_SM_set
                else:
                    def _aux_SM_set(chan, value):
                        return _SM_set(self._stack, chan, value)
                    self._SM_set = _aux_SM_set

    def update(self):
        time.sleep(self._short_timeout)
        try:
            self._attr_native_value = self._SM_get(self._chan)
        except Exception as ex:
            _LOGGER.error(self._card.domain + " %s update() failed, %s, %s, %s", self._type, ex, str(self._stack), str(self._chan))
            return
        if self._attr_native_value != 0:
            self._attr_icon = self._icons["on"]
        else:
            self._attr_icon = self._icons["off"]

    def set_native_value(self, value):
        try:
            self._SM_set(self._chan, value)
        except Exception as ex:
            _LOGGER.error(self._card.domain + " %s setting value failed, %s", self._type, ex)

## Lazy class, uses the set value as the get value
class Number_NOGET(Number):
    ## TODO implement
    def update(self):
        time.sleep(self._short_timeout)
        if self._attr_native_value != 0:
            self._attr_icon = self._icons["on"]
        else:
            self._attr_icon = self._icons["off"]

    def set_native_value(self, value):
        try:
            self._SM_set(self._chan, value)
            self._attr_native_value = value
        except Exception as ex:
            _LOGGER.error(self._card.domain + " %s setting value failed, %s", self._type, ex)

    def _sm_init(self):
        com = self._card.entity_map["number"][self._type]["com"]
        self._SM = self._card.api
        if inspect.isclass(self._SM):
            self._SM = self._card.api(self._stack)
            self._SM_set = getattr(self._SM, com["set"])
        else:
            def _aux_SM_set(*args):
                return getattr(self._SM, com["set"])(self._stack, *args)
            self._SM_set = _aux_SM_set
