DEFAULT_ICONS = {
        "on": "mdi:numeric-1",
        "off": "mdi:numeric-0",
}

import inspect
import logging
import time
import types
from datetime import datetime, timedelta
from inspect import signature

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.event import async_track_time_interval

from . import Card
from .const import (
    CONF_CHAN,
    CONF_NAME,
    CONF_STACK,
    CONF_TYPE,
    CONF_UPDATE_INTERVAL,
)
from .config_support import async_setup_entities

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities, card: Card):
    def create(config):
        return BinarySensor(
            hass=hass, name=config[CONF_NAME], stack=config[CONF_STACK],
            type=config[CONF_TYPE], chan=config[CONF_CHAN],
            update_interval=config.get(CONF_UPDATE_INTERVAL, 30), card=card,
        )
    await async_setup_entities(hass, entry, async_add_entities, "binary_sensor", create, card)

class BinarySensor(BinarySensorEntity):
    _attr_should_poll = False

    def __init__(self, name, stack, type, chan, hass, update_interval, card: Card):
        self._card = card
        sm_map = card.entity_map["binary_sensor"]
        generated_name = card.domain + str(stack) + "_" + type + "_" + str(chan)
        self._attr_unique_id = generate_entity_id("binary_sensor.{}", generated_name, current_ids=[])
        self._attr_name = name or generated_name
        self._stack = int(stack)
        self._type = type
        self._chan = int(chan)
        self._update_interval = float(update_interval)
        self._short_timeout = .05
        self._icons = DEFAULT_ICONS | sm_map[self._type].get("icon", {})
        self._attr_icon = self._icons["off"]
        self._uom = sm_map[self._type].get("uom", "")
        self._attr_is_on = False
        self._remove_hooks = []
        self.__SM__init()
        ### __CUSTOM_SETUP__ START
        ### __CUSTOM_SETUP__ END

    def __SM__init(self):
        com = self._card.entity_map["binary_sensor"][self._type]["com"]
        self._SM = self._card.api
        if inspect.isclass(self._SM):
            self._SM = self._card.api(self._stack)
            self._SM_get = getattr(self._SM, com["get"])
            if len(signature(self._SM_get).parameters) == 0:
                def _aux2_SM_get(self, _):
                    return getattr(self, com["get"])()
                self._SM_get = types.MethodType(_aux2_SM_get, self._SM)
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

    async def async_added_to_hass(self):
        async def update_state(_now: datetime) -> None:
            await self.async_update_ha_state(True)

        new_hook = async_track_time_interval(
            self.hass, update_state, timedelta(seconds=self._update_interval)
        )
        self._remove_hooks.append(new_hook)

    async def async_will_remove_from_hass(self):
        for remove_hook in self._remove_hooks:
            remove_hook()

    def update(self):
        time.sleep(self._short_timeout)
        try:
            value = self._SM_get(self._chan)
        except Exception as ex:
            _LOGGER.error(self._card.domain + " %s update() failed, %s, %s, %s", self._type, ex, str(self._stack), str(self._chan))
            return
        if not isinstance(value, int) or value not in (0, 1):
            _LOGGER.error(self._card.domain + " %s invalid reading %r, %s, %s", self._type, value, str(self._stack), str(self._chan))
            self._attr_is_on = None
            self._attr_icon = None
            return
        self._attr_is_on = bool(value)
        if self._attr_is_on:
            self._attr_icon = self._icons["on"]
        else:
            self._attr_icon = self._icons["off"]

    @property
    def native_unit_of_measurement(self):
        return self._uom

