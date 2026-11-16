"""Verify registry migration refuses conflicts without changing entries."""

from types import SimpleNamespace

import pytest
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import entity_registry as er

from SMcommonHA import Card, setup
from SMcommonHA.config_support import async_setup_entities


@pytest.fixture
def card():
    return Card("test_card", "TestCard", "test", "Test card", {}, None)


async def test_legacy_domain_conflict_does_not_migrate_any_entries(hass, card):
    registry = er.async_get(hass)
    first = registry.async_get_or_create("sensor", card.legacy_domain, "first")
    conflict = registry.async_get_or_create("sensor", card.legacy_domain, "conflict")
    existing = registry.async_get_or_create("sensor", card.domain, "conflict")

    with pytest.raises(RuntimeError, match="already exists"):
        await setup.async_setup(hass, {}, card)

    for entity in (first, conflict, existing):
        assert registry.async_get(entity.entity_id) == entity
    assert registry.async_get_entity_id("sensor", card.domain, "first") is None


async def test_ambiguous_suffixed_ids_do_not_create_or_modify_entities(hass, card):
    registry = er.async_get(hass)
    config = {
        "platform": "sensor",
        "name": "test0_temperature_1",
        "stack": 0,
        "type": "temperature",
        "chan": 1,
    }
    base = "sensor.test_card0_temperature_1"
    first = registry.async_get_or_create(
        "sensor", card.domain, base + "_2", original_name=config["name"]
    )
    second = registry.async_get_or_create(
        "sensor", card.domain, base + "_3", original_name=config["name"]
    )
    entry = SimpleNamespace(runtime_data=[config], entry_id="test", domain=card.domain)
    created = []

    with pytest.raises(ConfigEntryError, match="Ambiguous legacy entity"):
        await async_setup_entities(
            hass,
            entry,
            created.extend,
            "sensor",
            lambda _: pytest.fail("factory called"),
            card,
        )

    assert not created
    assert registry.async_get(first.entity_id) == first
    assert registry.async_get(second.entity_id) == second
    assert registry.async_get_entity_id("sensor", card.domain, base) is None
