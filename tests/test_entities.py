"""Verify shared entities against both styles of card API."""

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from sequent_ha_common import Card
from sequent_ha_common.binary_sensor import BinarySensor
from sequent_ha_common.button import Button
from sequent_ha_common.const import COM_NOGET
from sequent_ha_common.datetime import CardDateTime
from sequent_ha_common.number import Number, Number_NOGET
from sequent_ha_common.sensor import Sensor
from sequent_ha_common.switch import Switch


@pytest.fixture(params=["module", "class"])
def card_and_calls(request, monkeypatch):
    calls = []
    reading = {"value": 0, "rtc": (2026, 11, 15, 12, 0, 0)}
    monkeypatch.setattr("time.sleep", lambda _: None)

    class ModuleAPI:
        def get(self, stack, channel):
            calls.append(("get", stack, channel))
            return reading["value"]

        def set(self, stack, channel, value):
            calls.append(("set", stack, channel, value))

        def reset(self, stack, channel):
            calls.append(("reset", stack, channel))

        def reset_all(self, stack):
            calls.append(("reset_all", stack))

        def get_rtc(self, stack):
            calls.append(("get_rtc", stack))
            return reading["rtc"]

        def set_rtc(self, stack, *value):
            calls.append(("set_rtc", stack, *value))

    class ClassAPI:
        def __init__(self, stack):
            self.stack = stack

        def get(self, channel):
            calls.append(("get", self.stack, channel))
            return reading["value"]

        def set(self, channel, value):
            calls.append(("set", self.stack, channel, value))

        def reset(self, channel):
            calls.append(("reset", self.stack, channel))

        def reset_all(self):
            calls.append(("reset_all", self.stack))

        def get_rtc(self):
            calls.append(("get_rtc", self.stack))
            return reading["rtc"]

        def set_rtc(self, *value):
            calls.append(("set_rtc", self.stack, *value))

    entity_map = {
        "button": {
            "reset": {"com": {"set": "reset"}, "icon": {"off": "mdi:backup-restore"}},
            "reset_all": {"com": {"set": "reset_all"}},
        },
        "binary_sensor": {"opto": {"com": {"get": "get"}}},
        "datetime": {"rtc": {"com": {"get": "get_rtc", "set": "set_rtc"}}},
        "sensor": {"adc": {"com": {"get": "get"}}},
        "switch": {"relay": {"com": {"get": "get", "set": "set"}}},
        "number": {
            "dac": {
                "com": {"get": "get", "set": "set"},
                "min_value": 0,
                "max_value": 10,
                "step": 1,
            },
            "write_only": {
                "com": {"get": COM_NOGET, "set": "set"},
                "min_value": 0,
                "max_value": 10,
                "step": 1,
            },
        },
    }
    api = ModuleAPI() if request.param == "module" else ClassAPI
    return Card("test_card", "TestCard", "test", "Test card", entity_map, api), calls, reading


def test_button_calls_card_api_and_preserves_identity(card_and_calls):
    card, calls, _ = card_and_calls
    button = Button("counter reset", 2, "reset", 3, card)
    button.press()
    assert calls == [("reset", 2, 3)]
    assert button.unique_id == "button.test_card2_reset_3"
    assert button.name == "counter reset"
    assert button.icon == "mdi:backup-restore"


def test_button_without_channel(card_and_calls):
    card, calls, _ = card_and_calls
    button = Button(None, 2, "reset_all", 3, card)
    button.press()
    assert calls == [("reset_all", 2)]
    assert button.name == "test_card2_reset_all_3"
    assert button.icon == "mdi:button-pointer"


def test_button_failure_is_logged(card_and_calls, caplog):
    card, _, _ = card_and_calls
    button = Button("counter reset", 2, "reset", 3, card)

    def fail(_channel):
        raise OSError("reset failed")

    button._SM_set = fail
    with caplog.at_level(logging.ERROR):
        button.press()
    assert "test_card reset press failed, reset failed" in caplog.text


def test_rtc_reads_utc_and_only_writes_when_explicitly_set(card_and_calls):
    card, calls, reading = card_and_calls
    entity = CardDateTime("clock", 2, "rtc", 1, 30, card)
    assert entity.native_value == datetime(2026, 11, 15, 12, tzinfo=timezone.utc)
    entity.update()
    assert calls == [("get_rtc", 2), ("get_rtc", 2)]

    entity.set_value(datetime(2026, 11, 15, 13, 30, 1, 999, tzinfo=timezone(timedelta(hours=1))))
    assert calls[-1] == ("set_rtc", 2, 2026, 11, 15, 12, 30, 1)
    assert entity.native_value == datetime(2026, 11, 15, 12, 30, 1, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="time zone"):
        entity.set_value(datetime(2026, 11, 15))


def test_rtc_invalid_data_and_read_failure_recover(card_and_calls, caplog):
    card, _, reading = card_and_calls
    reading["rtc"] = (2026, 0, 1, 0, 0, 0)
    entity = CardDateTime("clock", 2, "rtc", 1, 30, card)
    assert entity.native_value is None
    assert "invalid RTC reading" in caplog.text
    reading["rtc"] = (2026, 1, 1)
    entity.update()
    assert entity.native_value is None
    reading["rtc"] = (2026, 1, 1, 0, 0, 0)
    entity.update()
    assert entity.native_value == datetime(2026, 1, 1, tzinfo=timezone.utc)
    get_rtc = entity._get_rtc

    def fail():
        raise OSError("I2C unavailable")

    entity._get_rtc = fail
    entity.update()
    assert entity.native_value is None
    assert "I2C unavailable" in caplog.text
    entity._get_rtc = get_rtc
    entity.update()
    assert entity.native_value == datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.mark.parametrize(("fold", "utc_hour"), [(0, 0), (1, 1)])
def test_rtc_set_preserves_dst_ambiguity(card_and_calls, fold, utc_hour):
    card, calls, _ = card_and_calls
    entity = CardDateTime("clock", 2, "rtc", 1, 30, card)
    local = datetime(2026, 10, 25, 2, 30, tzinfo=ZoneInfo("Europe/Prague"), fold=fold)
    entity.set_value(local)
    assert calls[-1] == ("set_rtc", 2, 2026, 10, 25, utc_hour, 30, 0)


def test_rtc_write_failure_does_not_change_state(card_and_calls):
    card, _, _ = card_and_calls
    entity = CardDateTime("clock", 2, "rtc", 1, 30, card)
    before = entity.native_value

    def fail(*_args):
        raise OSError("write failed")

    entity._set_rtc = fail
    with pytest.raises(OSError, match="write failed"):
        entity.set_value(datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert entity.native_value == before


def test_binary_sensor_rejects_bad_readings_and_recovers(card_and_calls, caplog):
    card, calls, reading = card_and_calls
    entity = BinarySensor("input", 2, "opto", 3, None, 30, card)
    for value, expected in ((0, False), (1, True), (None, None), (2, None), (0, False)):
        reading["value"] = value
        entity.update()
        assert entity.is_on is expected
    assert calls == [("get", 2, 3)] * 5
    assert "invalid reading None" in caplog.text
    assert "invalid reading 2" in caplog.text


def test_sensor_switch_and_number_use_the_selected_card_api(card_and_calls):
    card, calls, reading = card_and_calls
    reading["value"] = 1
    sensor = Sensor(None, "voltage", 2, "adc", 3, 30, card)
    switch = Switch("relay", 2, "relay", 3, None, card)
    number = Number(None, "output", 2, "dac", 3, card)
    sensor.update()
    switch.update()
    number.update()
    assert sensor.native_value == 1
    assert switch.is_on == 1
    assert number.native_value == 1
    switch.turn_on()
    switch.turn_off()
    number.set_native_value(4.0)
    assert calls == [
        ("get", 2, 3),
        ("get", 2, 3),
        ("get", 2, 3),
        ("get", 2, 3),
        ("set", 2, 3, 1),
        ("set", 2, 3, 0),
        ("set", 2, 3, 4),
    ]


def test_write_only_number_does_not_require_a_getter(card_and_calls):
    card, calls, _ = card_and_calls
    entity = Number_NOGET(None, "write only", 2, "write_only", 3, card)
    entity.set_native_value(4)
    entity.update()
    assert entity.native_value == 4
    assert calls == [("set", 2, 3, 4)]


def test_update_error_is_logged(card_and_calls, caplog):
    card, _, _ = card_and_calls
    entity = Sensor(None, "voltage", 2, "adc", 3, 30, card)

    def fail(_channel):
        raise OSError("read failed")

    entity._SM_get = fail
    with caplog.at_level(logging.ERROR):
        entity.update()
    assert "read failed" in caplog.text
