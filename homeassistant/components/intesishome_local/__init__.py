"""The IntesisHome Local integration."""
from __future__ import annotations

import asyncio

from pyintesishome_local import IntesisHomeApi, IntesisHomeEntity

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

PLATFORMS = ["climate"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up IntesisHome Local from a config entry."""
    # TODO Store an API object for your platforms to access
    session = async_get_clientsession(hass)
    api = IntesisHomeApi(session, entry.data["host"])
    await api.authenticate(entry.data["username"], entry.data["password"])
    entity = IntesisHomeEntity(api)
    await entity.get_datapoints()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entity

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
