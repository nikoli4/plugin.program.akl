# -*- coding: utf-8 -*-
"""Per-platform artwork presentation preferences for AKL skins.

Preferences are intentionally stored in AKL's userdata rather than in the skin so
virtual collections (Recently Played, Most Played, etc.) can carry the same choice
as the ROM's normal system/collection view.
"""
import json
import logging

from resources.lib import globals
from resources.lib.repositories import UnitOfWork, ROMsRepository

logger = logging.getLogger(__name__)

VALID_MODES = ('2d', '3dbox', 'cartridge')
DEFAULT_MODE = '2d'


def _load_preferences() -> dict:
    path = globals.g_PATHS.ARTWORK_PREFS_FILE_PATH
    if not path.exists():
        return {}
    try:
        raw = path.loadFileToStr()
        data = json.loads(raw) if raw else {}
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.warning('Unable to read artwork preferences: %s', exc)
        return {}


def _save_preferences(preferences: dict):
    try:
        globals.g_PATHS.ARTWORK_PREFS_FILE_PATH.writeAll(
            json.dumps(preferences, indent=2, sort_keys=True)
        )
    except Exception as exc:
        logger.error('Unable to save artwork preferences: %s', exc)


def get_mode(platform: str) -> str:
    if not platform:
        return DEFAULT_MODE
    mode = _load_preferences().get(platform, DEFAULT_MODE)
    return mode if mode in VALID_MODES else DEFAULT_MODE


def set_mode(platform: str, mode: str) -> bool:
    if not platform or mode not in VALID_MODES:
        return False
    preferences = _load_preferences()
    preferences[platform] = mode
    _save_preferences(preferences)
    logger.info('Artwork preference for platform "%s" set to "%s"', platform, mode)
    return True


def get_platform_for_rom(rom_id: str):
    if not rom_id:
        return None
    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        rom = ROMsRepository(uow).find_rom(rom_id)
        return rom.get_platform() if rom else None
