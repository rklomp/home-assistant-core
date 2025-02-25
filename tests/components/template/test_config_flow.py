"""Test the Switch config flow."""
from typing import Any
from unittest.mock import patch

import pytest
from pytest_unordered import unordered

from homeassistant import config_entries
from homeassistant.components.template import DOMAIN, async_setup_entry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


@pytest.mark.parametrize(
    (
        "template_type",
        "state_template",
        "template_state",
        "input_states",
        "input_attributes",
        "extra_input",
        "extra_options",
        "extra_attrs",
    ),
    (
        (
            "binary_sensor",
            "{{ states('binary_sensor.one') == 'on' or states('binary_sensor.two') == 'on' }}",
            "on",
            {"one": "on", "two": "off"},
            {},
            {},
            {},
            {},
        ),
        (
            "sensor",
            "{{ float(states('sensor.one')) + float(states('sensor.two')) }}",
            "50.0",
            {"one": "30.0", "two": "20.0"},
            {},
            {},
            {},
            {},
        ),
    ),
)
async def test_config_flow(
    hass: HomeAssistant,
    template_type,
    state_template,
    template_state,
    input_states,
    input_attributes,
    extra_input,
    extra_options,
    extra_attrs,
) -> None:
    """Test the config flow."""
    input_entities = ["one", "two"]
    for input_entity in input_entities:
        hass.states.async_set(
            f"{template_type}.{input_entity}",
            input_states[input_entity],
            input_attributes.get(input_entity, {}),
        )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": template_type},
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == template_type

    with patch(
        "homeassistant.components.template.async_setup_entry", wraps=async_setup_entry
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "My template",
                "state": state_template,
                **extra_input,
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "My template"
    assert result["data"] == {}
    assert result["options"] == {
        "name": "My template",
        "state": state_template,
        "template_type": template_type,
        **extra_options,
    }
    assert len(mock_setup_entry.mock_calls) == 1

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert config_entry.data == {}
    assert config_entry.options == {
        "name": "My template",
        "state": state_template,
        "template_type": template_type,
        **extra_options,
    }

    state = hass.states.get(f"{template_type}.my_template")
    assert state.state == template_state
    for key in extra_attrs:
        assert state.attributes[key] == extra_attrs[key]


def get_suggested(schema, key):
    """Get suggested value for key in voluptuous schema."""
    for k in schema:
        if k == key:
            if k.description is None or "suggested_value" not in k.description:
                return None
            return k.description["suggested_value"]
    # Wanted key absent from schema
    raise Exception


@pytest.mark.parametrize(
    (
        "template_type",
        "old_state_template",
        "new_state_template",
        "template_state",
        "input_states",
        "extra_options",
        "options_options",
    ),
    (
        (
            "binary_sensor",
            "{{ states('binary_sensor.one') == 'on' or states('binary_sensor.two') == 'on' }}",
            "{{ states('binary_sensor.one') == 'on' and states('binary_sensor.two') == 'on' }}",
            ["on", "off"],
            {"one": "on", "two": "off"},
            {},
            {},
        ),
        (
            "sensor",
            "{{ float(states('sensor.one')) + float(states('sensor.two')) }}",
            "{{ float(states('sensor.one')) - float(states('sensor.two')) }}",
            ["50.0", "10.0"],
            {"one": "30.0", "two": "20.0"},
            {},
            {},
        ),
    ),
)
async def test_options(
    hass: HomeAssistant,
    template_type,
    old_state_template,
    new_state_template,
    template_state,
    input_states,
    extra_options,
    options_options,
) -> None:
    """Test reconfiguring."""
    input_entities = ["one", "two"]

    for input_entity in input_entities:
        hass.states.async_set(
            f"{template_type}.{input_entity}", input_states[input_entity], {}
        )

    template_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My template",
            "state": old_state_template,
            "template_type": template_type,
            **extra_options,
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(f"{template_type}.my_template")
    assert state.state == template_state[0]

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == template_type
    assert get_suggested(result["data_schema"].schema, "state") == old_state_template
    assert "name" not in result["data_schema"].schema

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"state": new_state_template, **options_options},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "name": "My template",
        "state": new_state_template,
        "template_type": template_type,
        **extra_options,
    }
    assert config_entry.data == {}
    assert config_entry.options == {
        "name": "My template",
        "state": new_state_template,
        "template_type": template_type,
        **extra_options,
    }
    assert config_entry.title == "My template"

    # Check config entry is reloaded with new options
    await hass.async_block_till_done()
    state = hass.states.get(f"{template_type}.my_template")
    assert state.state == template_state[1]

    # Check we don't get suggestions from another entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": template_type},
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == template_type

    assert get_suggested(result["data_schema"].schema, "name") is None
    assert get_suggested(result["data_schema"].schema, "state") is None


@pytest.mark.parametrize(
    (
        "template_type",
        "state_template",
        "extra_user_input",
        "input_states",
        "template_states",
        "extra_attributes",
        "listeners",
    ),
    (
        (
            "binary_sensor",
            "{{ states.binary_sensor.one.state == 'on' or states.binary_sensor.two.state == 'on' }}",
            {},
            {"one": "on", "two": "off"},
            ["off", "on"],
            [{}, {}],
            [["one", "two"], ["one"]],
        ),
        (
            "sensor",
            "{{ float(states('sensor.one')) + float(states('sensor.two')) }}",
            {},
            {"one": "30.0", "two": "20.0"},
            ["unavailable", "50.0"],
            [{}, {}],
            [["one"], ["one", "two"]],
        ),
    ),
)
async def test_config_flow_preview(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    template_type: str,
    state_template: str,
    extra_user_input: dict[str, Any],
    input_states: list[str],
    template_states: str,
    extra_attributes: list[dict[str, Any]],
    listeners: list[list[str]],
) -> None:
    """Test the config flow preview."""
    client = await hass_ws_client(hass)

    input_entities = ["one", "two"]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": template_type},
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == template_type
    assert result["errors"] is None
    assert result["preview"] == "template"

    await client.send_json_auto_id(
        {
            "type": "template/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "config_flow",
            "user_input": {"name": "My template", "state": state_template}
            | extra_user_input,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    msg = await client.receive_json()
    assert msg["event"] == {
        "attributes": {"friendly_name": "My template"} | extra_attributes[0],
        "listeners": {
            "all": False,
            "domains": [],
            "entities": unordered([f"{template_type}.{_id}" for _id in listeners[0]]),
            "time": False,
        },
        "state": template_states[0],
    }

    for input_entity in input_entities:
        hass.states.async_set(
            f"{template_type}.{input_entity}", input_states[input_entity], {}
        )

    msg = await client.receive_json()
    assert msg["event"] == {
        "attributes": {"friendly_name": "My template"}
        | extra_attributes[0]
        | extra_attributes[1],
        "listeners": {
            "all": False,
            "domains": [],
            "entities": unordered([f"{template_type}.{_id}" for _id in listeners[1]]),
            "time": False,
        },
        "state": template_states[1],
    }
    assert len(hass.states.async_all()) == 2


EARLY_END_ERROR = "invalid template (TemplateSyntaxError: unexpected 'end of template')"


@pytest.mark.parametrize(
    ("template_type", "state_template", "extra_user_input", "error"),
    [
        ("binary_sensor", "{{", {}, {"state": EARLY_END_ERROR}),
        ("sensor", "{{", {}, {"state": EARLY_END_ERROR}),
        (
            "sensor",
            "",
            {"device_class": "aqi", "unit_of_measurement": "cats"},
            {
                "unit_of_measurement": (
                    "'cats' is not a valid unit for device class 'aqi'; "
                    "expected no unit of measurement"
                ),
            },
        ),
        (
            "sensor",
            "",
            {"device_class": "temperature", "unit_of_measurement": "cats"},
            {
                "unit_of_measurement": (
                    "'cats' is not a valid unit for device class 'temperature'; "
                    "expected one of 'K', '°C', '°F'"
                ),
            },
        ),
        (
            "sensor",
            "",
            {"device_class": "timestamp", "state_class": "measurement"},
            {
                "state_class": (
                    "'measurement' is not a valid state class for device class "
                    "'timestamp'; expected no state class"
                ),
            },
        ),
        (
            "sensor",
            "",
            {"device_class": "aqi", "state_class": "total"},
            {
                "state_class": (
                    "'total' is not a valid state class for device class "
                    "'aqi'; expected 'measurement'"
                ),
            },
        ),
        (
            "sensor",
            "",
            {"device_class": "energy", "state_class": "measurement"},
            {
                "state_class": (
                    "'measurement' is not a valid state class for device class "
                    "'energy'; expected one of 'total', 'total_increasing'"
                ),
                "unit_of_measurement": (
                    "'None' is not a valid unit for device class 'energy'; "
                    "expected one of 'GJ', 'kWh', 'MJ', 'MWh', 'Wh'"
                ),
            },
        ),
    ],
)
async def test_config_flow_preview_bad_input(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    template_type: str,
    state_template: str,
    extra_user_input: dict[str, str],
    error: str,
) -> None:
    """Test the config flow preview."""
    client = await hass_ws_client(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": template_type},
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == template_type
    assert result["errors"] is None
    assert result["preview"] == "template"

    await client.send_json_auto_id(
        {
            "type": "template/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "config_flow",
            "user_input": {"name": "My template", "state": state_template}
            | extra_user_input,
        }
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"] == {
        "code": "invalid_user_input",
        "message": error,
    }


@pytest.mark.parametrize(
    (
        "template_type",
        "state_template",
        "extra_user_input",
    ),
    (
        (
            "sensor",
            "{{ states('sensor.one') }}",
            {"unit_of_measurement": "°C"},
        ),
    ),
)
async def test_config_flow_preview_bad_state(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    template_type: str,
    state_template: str,
    extra_user_input: dict[str, Any],
) -> None:
    """Test the config flow preview."""
    client = await hass_ws_client(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.MENU

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"next_step_id": template_type},
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == template_type
    assert result["errors"] is None
    assert result["preview"] == "template"

    await client.send_json_auto_id(
        {
            "type": "template/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "config_flow",
            "user_input": {"name": "My template", "state": state_template}
            | extra_user_input,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    msg = await client.receive_json()
    assert msg["event"] == {
        "error": (
            "Sensor None has device class 'None', state class 'None' unit '°C' "
            "and suggested precision 'None' thus indicating it has a numeric "
            "value; however, it has the non-numeric value: 'unknown' (<class "
            "'str'>)"
        ),
    }


@pytest.mark.parametrize(
    (
        "template_type",
        "old_state_template",
        "new_state_template",
        "extra_config_flow_data",
        "extra_user_input",
        "input_states",
        "template_state",
        "extra_attributes",
        "listeners",
    ),
    [
        (
            "binary_sensor",
            "{{ states('binary_sensor.one') == 'on' or states('binary_sensor.two') == 'on' }}",
            "{{ states('binary_sensor.one') == 'on' and states('binary_sensor.two') == 'on' }}",
            {},
            {},
            {"one": "on", "two": "off"},
            "off",
            {},
            ["one", "two"],
        ),
        (
            "sensor",
            "{{ float(states('sensor.one')) + float(states('sensor.two')) }}",
            "{{ float(states('sensor.one')) - float(states('sensor.two')) }}",
            {},
            {},
            {"one": "30.0", "two": "20.0"},
            "10.0",
            {},
            ["one", "two"],
        ),
    ],
)
async def test_option_flow_preview(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    template_type: str,
    old_state_template: str,
    new_state_template: str,
    extra_config_flow_data: dict[str, Any],
    extra_user_input: dict[str, Any],
    input_states: list[str],
    template_state: str,
    extra_attributes: dict[str, Any],
    listeners: list[str],
) -> None:
    """Test the option flow preview."""
    client = await hass_ws_client(hass)

    input_entities = input_entities = ["one", "two"]

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My template",
            "state": old_state_template,
            "template_type": template_type,
        }
        | extra_config_flow_data,
        title="My template",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None
    assert result["preview"] == "template"

    for input_entity in input_entities:
        hass.states.async_set(
            f"{template_type}.{input_entity}", input_states[input_entity], {}
        )

    await client.send_json_auto_id(
        {
            "type": "template/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "options_flow",
            "user_input": {"state": new_state_template} | extra_user_input,
        }
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] is None

    msg = await client.receive_json()
    assert msg["event"] == {
        "attributes": {"friendly_name": "My template"} | extra_attributes,
        "listeners": {
            "all": False,
            "domains": [],
            "entities": unordered([f"{template_type}.{_id}" for _id in listeners]),
            "time": False,
        },
        "state": template_state,
    }
    assert len(hass.states.async_all()) == 3


async def test_option_flow_sensor_preview_config_entry_removed(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test the option flow preview where the config entry is removed."""
    client = await hass_ws_client(hass)

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My template",
            "state": "Hello!",
            "template_type": "sensor",
        },
        title="My template",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None
    assert result["preview"] == "template"

    await hass.config_entries.async_remove(config_entry.entry_id)

    await client.send_json_auto_id(
        {
            "type": "template/start_preview",
            "flow_id": result["flow_id"],
            "flow_type": "options_flow",
            "user_input": {"state": "Goodbye!"},
        }
    )
    msg = await client.receive_json()
    assert not msg["success"]
    assert msg["error"] == {"code": "unknown_error", "message": "Unknown error"}
