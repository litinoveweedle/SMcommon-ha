"""Test both integrations together when their checkouts are provided."""

import importlib
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.loader import async_clear_custom_components_cache
from homeassistant.setup import async_setup_component


@pytest.fixture
def hass_config_dir(tmp_path):
    paths = {
        "smioplus": os.environ.get("SMIOPLUS_REPO"),
        "smmultiio": os.environ.get("SMMULTIIO_REPO"),
    }
    if not any(paths.values()):
        pytest.skip("Set SMIOPLUS_REPO and SMMULTIIO_REPO to test coexistence")
    if not all(paths.values()):
        pytest.fail("Both SMIOPLUS_REPO and SMMULTIIO_REPO are required")
    custom = tmp_path / "custom_components"
    custom.mkdir()
    for domain, project in paths.items():
        assert project is not None
        component = Path(project) / "custom_components" / domain
        if not component.is_dir():
            pytest.fail(f"Integration directory not found: {component}")
        (custom / domain).symlink_to(component)
    return str(tmp_path)


async def test_two_cards_use_separate_apis_and_devices(hass, monkeypatch):
    monkeypatch.syspath_prepend(hass.config.config_dir)
    async_clear_custom_components_cache(hass)
    io = importlib.import_module("custom_components.smioplus")
    multi = importlib.import_module("custom_components.smmultiio")
    states = {"io": 1, "multi": 0}
    monkeypatch.setattr(io.CARD, "api", SimpleNamespace(getOptoCh=lambda stack, chan: states["io"]))

    class MultiAPI:
        def __init__(self, stack):
            self.stack = stack

        def get_opto(self, chan):
            return states["multi"]

    monkeypatch.setattr(multi.CARD, "api", MultiAPI)
    config = {
        "smioplus": [{"stack": "0", "opto_1": None}],
        "smmultiio": [{"stack": "0", "opto_in_1": None}],
    }
    assert await async_setup_component(hass, "smioplus", config)
    assert await async_setup_component(hass, "smmultiio", config)
    await hass.async_block_till_done()
    registry = entity_registry.async_get(hass)
    io_id = registry.async_get_entity_id("binary_sensor", "smioplus", "binary_sensor.smioplus0_opto_1")
    multi_id = registry.async_get_entity_id("binary_sensor", "smmultiio", "binary_sensor.smmultiio0_opto_in_1")
    assert io_id and multi_id
    await async_update_entity(hass, io_id)
    await async_update_entity(hass, multi_id)
    assert hass.states.get(io_id).state == "on"
    assert hass.states.get(multi_id).state == "off"
    states.update(io=0, multi=1)
    await async_update_entity(hass, io_id)
    await async_update_entity(hass, multi_id)
    assert hass.states.get(io_id).state == "off"
    assert hass.states.get(multi_id).state == "on"
    assert registry.async_get(io_id).device_id != registry.async_get(multi_id).device_id
