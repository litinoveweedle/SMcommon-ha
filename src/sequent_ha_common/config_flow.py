"""UI configuration for a Sequent card."""

import math

import probatio as p
from homeassistant import config_entries
from homeassistant.helpers import selector

from . import Card
from .config_support import (
    available_entities,
    import_yaml_card,
)
from .const import (
    CONF_ENTITIES,
    CONF_INTERVALS,
    CONF_STACK,
    CONF_UPDATE_INTERVAL,
    DEFAULT_INTERVAL,
)


def valid_interval(value):
    """Reject intervals that cannot be used with a timer."""
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise p.Invalid("update interval must be finite and positive")
    return value


class SequentConfigFlow(config_entries.ConfigFlow):
    """Create one config entry per card address."""

    VERSION = 1
    card: Card

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return await self._create_card(import_yaml_card(self.card, user_input))
        return self.async_show_form(
            step_id="user",
            data_schema=p.Schema(
                {
                    p.Required(CONF_STACK, default=0): p.All(
                        p.Coerce(int), p.Range(min=0, max=7)
                    )
                }
            ),
        )

    async def async_step_import(self, user_input):
        return await self._create_card(user_input)

    async def _create_card(self, card):
        stack = card[CONF_STACK]
        await self.async_set_unique_id(str(stack))
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"{self.card.full_name} - stack {stack}", data=card
        )


class SequentOptionsFlow(config_entries.OptionsFlowWithReload):
    """Select entities and configure their update intervals."""

    def __init__(self, card: Card):
        self.card = card

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            self._selected = user_input[CONF_ENTITIES]
            return await self.async_step_intervals()

        available = available_entities(self.card, self.config_entry.data[CONF_STACK])
        selected = self.config_entry.options.get(
            CONF_ENTITIES, list(self.config_entry.data[CONF_ENTITIES])
        )
        return self.async_show_form(
            step_id="init",
            data_schema=p.Schema(
                {
                    p.Required(
                        CONF_ENTITIES, default=selected
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value=key, label=key)
                                for key in available
                            ],
                            multiple=True,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_intervals(self, user_input=None):
        available = available_entities(self.card, self.config_entry.data[CONF_STACK])
        selected = self._selected
        if user_input is not None:
            return self.async_create_entry(
                title="", data={CONF_ENTITIES: selected, CONF_INTERVALS: user_input}
            )
        imported = self.config_entry.data[CONF_ENTITIES]
        intervals = self.config_entry.options.get(CONF_INTERVALS, {})
        interval_entities = [
            key
            for key in selected
            if available[key]["platform"] in ("sensor", "binary_sensor", "datetime")
        ]
        if not interval_entities:
            return self.async_create_entry(
                title="", data={CONF_ENTITIES: selected, CONF_INTERVALS: {}}
            )
        return self.async_show_form(
            step_id="intervals",
            data_schema=p.Schema(
                {
                    p.Required(
                        key,
                        default=intervals.get(
                            key,
                            imported.get(key, {}).get(
                                CONF_UPDATE_INTERVAL, DEFAULT_INTERVAL
                            ),
                        ),
                    ): p.All(p.Coerce(float), valid_interval)
                    for key in interval_entities
                }
            ),
        )
