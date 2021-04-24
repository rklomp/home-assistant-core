"""The IntesisHome Local climate entity."""
import logging
from typing import Callable, Coroutine

from pyintesishome_local import IntesisHomeEntity

from homeassistant.components.intesishome.climate import IntesisAC
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[], Coroutine],
) -> None:
    """Set up IntesisHome Local climate."""

    controller: IntesisHomeEntity = hass.data[DOMAIN][config_entry.entry_id]
    device_info: dict = await controller.get_info()

    async_add_entities(
        [IntesisLocalAC(config_entry.unique_id, device_info, controller)]
    )


class IntesisLocalAC(IntesisAC):
    """IntesisLocal AC Entity."""

    def __init__(
        self, unique_id: str, device_info: dict, controller: IntesisHomeEntity
    ):
        """Init Entity."""
        self._device_info: dict = device_info
        ih_device: dict = {"name": device_info["ownSSID"]}

        super().__init__(unique_id, ih_device, controller)

    @property
    def device_info(self) -> dict:
        """Return the device information."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_info["ownSSID"],
            "manufacturer": "Intesis",
            "model": self._device_info["deviceModel"],
            "sw_version": self._device_info["fwVersion"],
        }
