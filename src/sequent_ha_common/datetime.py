"""RTC datetime entities for Sequent card integrations."""

import inspect
import logging
from datetime import datetime, timedelta, timezone
from functools import partial

from homeassistant.components.datetime import DateTimeEntity
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.event import async_track_time_interval

from . import Card
from .config_support import async_setup_entities
from .const import CONF_CHAN, CONF_NAME, CONF_STACK, CONF_TYPE, CONF_UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)
DEFAULT_ICONS = {"on": "mdi:clock", "off": "mdi:clock-alert"}


async def async_setup_entry(hass, entry, async_add_entities, card: Card):
    def create(config):
        return CardDateTime(
            name=config[CONF_NAME],
            stack=config[CONF_STACK],
            type=config[CONF_TYPE],
            chan=config[CONF_CHAN],
            update_interval=config.get(CONF_UPDATE_INTERVAL, 30),
            card=card,
        )

    await async_setup_entities(
        hass, entry, async_add_entities, "datetime", create, card
    )


class CardDateTime(DateTimeEntity):
    """A card RTC whose calendar fields represent UTC."""

    _attr_should_poll = False

    def __init__(self, name, stack, type, chan, update_interval, card: Card):
        self._card = card
        self._stack = int(stack)
        self._type = type
        self._chan = int(chan)
        self._update_interval = float(update_interval)
        generated_name = card.domain + str(stack) + "_" + type + "_" + str(chan)
        self._attr_unique_id = generate_entity_id(
            "datetime.{}", generated_name, current_ids=[]
        )
        self._attr_name = name or generated_name
        metadata = card.entity_map["datetime"][type]
        self._icons = DEFAULT_ICONS | metadata.get("icon", {})

        api = card.api
        if inspect.isclass(api):
            api = card.api(self._stack)
            self._get_rtc = getattr(api, metadata["com"]["get"])
            self._set_rtc = getattr(api, metadata["com"]["set"])
        else:
            self._get_rtc = partial(getattr(api, metadata["com"]["get"]), self._stack)
            self._set_rtc = partial(getattr(api, metadata["com"]["set"]), self._stack)

        self._attr_native_value = self._read_rtc()
        self._attr_icon = self._icons["on" if self._attr_native_value else "off"]

    def _read_rtc(self):
        try:
            value = self._get_rtc()
            if (
                not isinstance(value, (tuple, list))
                or len(value) != 6
                or any(
                    not isinstance(part, int) or isinstance(part, bool)
                    for part in value
                )
            ):
                raise ValueError(f"expected six integer fields, got {value!r}")
            return datetime(*value, tzinfo=timezone.utc)
        except (TypeError, ValueError, OverflowError) as err:
            _LOGGER.error(
                "%s %s invalid RTC reading for stack %s: %s",
                self._card.domain,
                self._type,
                self._stack,
                err,
            )
            return None

    async def async_added_to_hass(self):
        await super().async_added_to_hass()

        async def update_state(_now: datetime) -> None:
            await self.async_update_ha_state(True)

        self.async_on_remove(
            async_track_time_interval(
                self.hass, update_state, timedelta(seconds=self._update_interval)
            )
        )

    def update(self):
        try:
            self._attr_native_value = self._read_rtc()
        except OSError as err:
            _LOGGER.error(
                "%s %s RTC read failed for stack %s: %s",
                self._card.domain,
                self._type,
                self._stack,
                err,
            )
            self._attr_native_value = None
        self._attr_icon = self._icons["on" if self._attr_native_value else "off"]

    def set_value(self, value: datetime) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("RTC datetime must include a time zone")
        utc_value = value.astimezone(timezone.utc).replace(microsecond=0)
        self._set_rtc(
            utc_value.year,
            utc_value.month,
            utc_value.day,
            utc_value.hour,
            utc_value.minute,
            utc_value.second,
        )
        self._attr_native_value = utc_value
        self._attr_icon = self._icons["on"]

    async def async_set_value(self, value: datetime) -> None:
        await super().async_set_value(value)
        self.async_write_ha_state()
