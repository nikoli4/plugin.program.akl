# -*- coding: utf-8 -*-
#
# Advanced Kodi Launcher: Commands (romcollection launcher management)
#
# Copyright (c) Wintermute0110 <wintermute0110@gmail.com> / Chrisism <crizizz@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# --- Python standard library ---
from __future__ import unicode_literals
from __future__ import division

import logging
import collections
import random
import os
import re

import xbmc
import xbmcaddon
import xbmcvfs

from akl.utils import kodi
from akl import settings, constants

from resources.lib.commands.mediator import AppMediator
from resources.lib import globals
from resources.lib.repositories import UnitOfWork, AklAddonRepository, LaunchersRepository
from resources.lib.repositories import ROMCollectionRepository, ROMsRepository, SourcesRepository
from resources.lib.domain import AklAddon, ROMLauncherAddon, ROMLauncherAddonFactory

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------------------------------
# Launcher management.
# -------------------------------------------------------------------------------------------------
@AppMediator.register('ADD_LAUNCHER')
def cmd_add_launcher(args):
    options = collections.OrderedDict()
    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        repository = AklAddonRepository(uow)
        addons = repository.find_all_launcher_addons()

        for addon in addons:
            options[addon] = addon.get_name()
    
    s = kodi.translate(41106)
    selected_option: AklAddon = kodi.OrdDictionaryDialog().select(s, options)
    
    if selected_option is None:
        # Standalone Add Launcher has no parent ROM menu.
        logger.debug('ADD_LAUNCHER: Cancelled.')
        return
    
    # >> Execute subcommand. May be atomic, maybe a submenu.
    logger.debug(f'Selected {selected_option.get_id()}')
    
    selected_launcher = ROMLauncherAddonFactory.create(selected_option, {})

    # Apply the configured default emulator directory.
    default_emulators_root = settings.getSetting(
        'setup_default_emulators_root'
    )

    if default_emulators_root:
        kodi.set_windowprop(
            'AKL.SetupWizard.DefaultEmulatorsRoot',
            default_emulators_root
        )

        logger.info(
            f'ADD_LAUNCHER: Set default Emulators root '
            f'for launcher configuration: "{default_emulators_root}".'
        )

    selected_launcher.configure(args)


@AppMediator.register('EDIT_LAUNCHER')
def cmd_edit_launcher(args):
    logger.debug('EDIT_LAUNCHER')
    launcher_id: str = args['launcher_id'] if 'launcher_id' in args else None
    
    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        repository = LaunchersRepository(uow)
        launcher = repository.find(launcher_id)

    launcher.configure(args)


@AppMediator.register('DELETE_LAUNCHER')
def cmd_delete_launcher(args):
    logger.debug('DELETE_LAUNCHER')
    launcher_id: str = args['launcher_id'] if 'launcher_id' in args else None
    
    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        repository = LaunchersRepository(uow)
        launcher = repository.find(launcher_id)

        confirmed = kodi.dialog_yesno(kodi.translate(41066).format(launcher.get_name()))
        if not confirmed:
            return
        
        repository.delete_launcher(launcher)
        uow.commit()
        kodi.refresh_container()


# -------------------------------------------------------------------------------------------------
# Launcher association.
# -------------------------------------------------------------------------------------------------
@AppMediator.register('EDIT_SOURCE_LAUNCHERS')
def cmd_manage_source_launchers(args):
    logger.debug('EDIT_SOURCE_LAUNCHERS: SHOW MENU')
    source_id: str = args['source_id'] if 'source_id' in args else None
    
    selected_option = None
    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        repository = SourcesRepository(uow)
        source = repository.find(source_id)
        
    launchers = source.get_launchers()
    default_launcher = next((lr for lr in launchers if lr.is_default()), launchers[0]) if len(launchers) > 0 else None
    default_launcher_name = default_launcher.get_name() if default_launcher is not None else 'None'
    
    options = collections.OrderedDict()
    options['ADD_SOURCE_LAUNCHER'] = kodi.translate(42026)
    options['REMOVE_SOURCE_LAUNCHER'] = kodi.translate(42028)
    options['SET_DEFAULT_SOURCE_LAUNCHER'] = kodi.translate(42029).format(default_launcher_name)
        
    s = kodi.translate(41100).format(source.get_name())
    selected_option = kodi.OrdDictionaryDialog().select(s, options)
    if selected_option is None:
        # >> Exits context menu
        logger.debug('EDIT_SOURCE_LAUNCHERS: Selected None. Closing context menu')
        AppMediator.sync_cmd('EDIT_SOURCE', args)
        return
    
    # >> Execute subcommand. May be atomic, maybe a submenu.
    logger.debug(f'EDIT_SOURCE_LAUNCHERS: Selected {selected_option}')
    AppMediator.sync_cmd(selected_option, args)


@AppMediator.register('EDIT_ROMCOLLECTION_LAUNCHERS')
def cmd_manage_romcollection_launchers(args):
    logger.debug('EDIT_ROMCOLLECTION_LAUNCHERS: cmd_manage_romcollection_launchers() SHOW MENU')
    romcollection_id: str = args['romcollection_id'] if 'romcollection_id' in args else None
    
    selected_option = None
    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        repository = ROMCollectionRepository(uow)
        romcollection = repository.find_romcollection(romcollection_id)
        
    launchers = romcollection.get_launchers()
    default_launcher = next((lc for lc in launchers if lc.is_default()), launchers[0]) if len(launchers) > 0 else None
    default_launcher_name = default_launcher.get_name() if default_launcher is not None else 'None'
    
    options = collections.OrderedDict()
    options['ADD_COLLECTION_LAUNCHER'] = kodi.translate(42026)
    options['REMOVE_COLLECTION_LAUNCHER'] = kodi.translate(42028)
    options['SET_DEFAULT_COLLECTION_LAUNCHER'] = kodi.translate(42029).format(default_launcher_name)
        
    s = kodi.translate(41100).format(romcollection.get_name())
    selected_option = kodi.OrdDictionaryDialog().select(s, options)
    if selected_option is None:
        # >> Exits context menu
        logger.debug('EDIT_ROMCOLLECTION_LAUNCHERS: Selected None. Closing context menu')
        AppMediator.sync_cmd('EDIT_ROMCOLLECTION', args)
        return
    
    # >> Execute subcommand. May be atomic, maybe a submenu.
    logger.debug(f'EDIT_ROMCOLLECTION_LAUNCHERS: Selected {selected_option}')
    AppMediator.sync_cmd(selected_option, args)


@AppMediator.register('EDIT_ROM_LAUNCHERS')
def cmd_manage_rom_launchers(args):
    logger.debug('EDIT_ROM_LAUNCHERS: cmd_manage_rom_launchers() SHOW MENU')
    rom_id: str = args['rom_id'] if 'rom_id' in args else None
    
    selected_option = None
    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        repository = ROMsRepository(uow)
        rom = repository.find_rom(rom_id)
        
    launchers = rom.get_launchers()
    default_launcher = next((lc for lc in launchers if lc.is_default()), launchers[0]) if len(launchers) > 0 else None
    default_launcher_name = default_launcher.get_name() if default_launcher is not None else kodi.translate(20010)
    
    options = collections.OrderedDict()
    options['ADD_ROM_LAUNCHER'] = kodi.translate(42026)
    options['REMOVE_ROM_LAUNCHER'] = kodi.translate(42028)
    options['SET_DEFAULT_ROM_LAUNCHER'] = kodi.translate(42029).format(default_launcher_name)
        
    s = kodi.translate(41100).format(rom.get_name())
    selected_option = kodi.OrdDictionaryDialog().select(s, options)
    if selected_option is None:
        # >> Exits context menu
        logger.debug('Selected None. Closing context menu')
        AppMediator.sync_cmd('EDIT_ROM', args)
        return
    
    # >> Execute subcommand. May be atomic, maybe a submenu.
    logger.debug(f'Selected {selected_option}')
    AppMediator.sync_cmd(selected_option, args)
    

# --- Sub commands ---
@AppMediator.register('ADD_ROM_LAUNCHER')
def cmd_add_rom_launchers(args):
    rom_id: str = args['rom_id'] if 'rom_id' in args else None
    
    options = collections.OrderedDict()
    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        repository = LaunchersRepository(uow)
        rom_repository = ROMsRepository(uow)
        
        launchers = repository.find_all()
        rom = rom_repository.find_rom(rom_id)

        for launcher in launchers:
            options[launcher] = kodi.get_listitem(launcher.get_name(), launcher.get_addon_name())
        options["NEW"] = kodi.translate(42090)
        
        s = kodi.translate(41101)
        selected_option = kodi.OrdDictionaryDialog().select(s, options, use_details=True)
        
        if selected_option is None:
            # >> Exits context menu
            logger.debug('Selected None. Closing context menu')
            AppMediator.sync_cmd('EDIT_ROM_LAUNCHERS', args)
            return
        
        if selected_option == "NEW":
            args["entity_type"] = constants.OBJ_ROM
            args["entity_id"] = rom_id
            AppMediator.sync_cmd("ADD_LAUNCHER", args)
            return
        
        selected_option: ROMLauncherAddon = selected_option
        logger.debug(f'Selected {selected_option.get_id()}')
        is_default = kodi.dialog_yesno(kodi.translate(41171).format(selected_option.get_name()))
        
        rom.add_launcher(launcher, is_default)
        rom_repository.update_rom(rom)
        logger.info(f'Added launcher#{selected_option.get_id()} to ROM {rom.get_id()}')
        uow.commit()
    
    kodi.notify(kodi.translate(41109).format(selected_option.get_name()))
    AppMediator.sync_cmd('EDIT_ROM_LAUNCHERS', args)


@AppMediator.register('ADD_SOURCE_LAUNCHER')
def cmd_add_source_launchers(args):
    source_id: str = args['source_id'] if 'source_id' in args else None
        
    options = collections.OrderedDict()
    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        repository = LaunchersRepository(uow)
        source_repository = SourcesRepository(uow)
        
        launchers = repository.find_all()
        source = source_repository.find(source_id)

        for launcher in launchers:
            options[launcher] = kodi.get_listitem(launcher.get_name(), launcher.get_addon_name())
        options["NEW"] = kodi.translate(42090)
    
        s = kodi.translate(41101)
        selected_option: ROMLauncherAddon = kodi.OrdDictionaryDialog().select(s, options, use_details=True)
        
        if selected_option is None:
            # >> Exits context menu
            logger.debug('ADD_SOURCE_LAUNCHER: Selected None. Closing context menu')
            AppMediator.sync_cmd('EDIT_SOURCE_LAUNCHERS', args)
            return
        
        if selected_option == "NEW":
            args["entity_type"] = constants.OBJ_SOURCE
            args["entity_id"] = source_id
            AppMediator.sync_cmd("ADD_LAUNCHER", args)
            return
        
        logger.debug(f'ADD_SOURCE_LAUNCHER: Selected {selected_option.get_id()}')
        is_default = kodi.dialog_yesno(kodi.translate(41171).format(selected_option.get_name()))
        
        source.add_launcher(selected_option, is_default)
        if kodi.dialog_yesno(kodi.translate(41050)):
            source.import_data_dic(selected_option.get_setting('romcollection'))
            
        source_repository.update_source(source)
        logger.info(f'Added launcher#{selected_option.get_id()} to Source {source.get_id()}')
        uow.commit()

    kodi.notify(kodi.translate(41109).format(selected_option.get_name()))
    AppMediator.sync_cmd('EDIT_SOURCE_LAUNCHERS', args)


@AppMediator.register('ADD_COLLECTION_LAUNCHER')
def cmd_add_romcollection_launchers(args):
    romcollection_id: str = args['romcollection_id'] if 'romcollection_id' in args else None
    
    metadata_updated = False
    options = collections.OrderedDict()
    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        repository = LaunchersRepository(uow)
        romcollection_repository = ROMCollectionRepository(uow)
        
        launchers = repository.find_all()
        romcollection = romcollection_repository.find_romcollection(romcollection_id)

        for launcher in launchers:
            options[launcher] = kodi.get_listitem(launcher.get_name(), launcher.get_addon_name())
        options["NEW"] = kodi.translate(42090)
           
        s = kodi.translate(41101)
        selected_option: ROMLauncherAddon = kodi.OrdDictionaryDialog().select(s, options, use_details=True)
    
        if selected_option is None:
            # >> Exits context menu
            logger.debug('ADD_COLLECTION_LAUNCHER: Selected None. Closing context menu')
            AppMediator.sync_cmd('EDIT_ROMCOLLECTION_LAUNCHERS', args)
            return
    
        if selected_option == "NEW":
            args["entity_type"] = constants.OBJ_ROMCOLLECTION
            args["entity_id"] = romcollection_id
            AppMediator.sync_cmd("ADD_LAUNCHER", args)
            return
        
        logger.debug(f'ADD_COLLECTION_LAUNCHER: Selected {selected_option.get_id()}')
        is_default = kodi.dialog_yesno(kodi.translate(41171).format(selected_option.get_name()))
        
        romcollection.add_launcher(selected_option, is_default)
        if kodi.dialog_yesno(kodi.translate(41050)):
            romcollection.import_data_dic(selected_option.get_setting('romcollection'))
            metadata_updated = True
            
        romcollection_repository.update_romcollection(romcollection)
        logger.info(f'Added launcher#{selected_option.get_id()} to ROMCollection {romcollection.get_id()}')
        uow.commit()
    
    if metadata_updated:
        AppMediator.async_cmd('RENDER_CATEGORY_VIEW', {'category_id': romcollection.get_parent_id()})
        
    kodi.notify(kodi.translate(41109).format(selected_option.get_name()))
    AppMediator.sync_cmd('EDIT_ROMCOLLECTION_LAUNCHERS', args)

          
@AppMediator.register('REMOVE_COLLECTION_LAUNCHER')
def cmd_remove_romcollection_launchers(args):
    romcollection_id: str = args['romcollection_id'] if 'romcollection_id' in args else None
    
    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        romcollection_repository = ROMCollectionRepository(uow)
        romcollection = romcollection_repository.find_romcollection(romcollection_id)
    
        launchers = romcollection.get_launchers()
        if len(launchers) == 0:
            kodi.notify(kodi.translate(41003))
            AppMediator.sync_cmd('EDIT_ROMCOLLECTION_LAUNCHERS', args)
            return
        
        options = collections.OrderedDict()
        for launcher in launchers:
            options[launcher] = kodi.get_listitem(launcher.get_name(), launcher.get_addon_name())
        
        s = kodi.translate(41103)
        selected_option: ROMLauncherAddon = kodi.OrdDictionaryDialog().select(s, options, use_details=True)
        
        if selected_option is None:
            # >> Exits context menu
            logger.debug('REMOVE_COLLECTION_LAUNCHER: cmd_remove_romcollection_launchers() Selected None. Closing context menu')
            AppMediator.sync_cmd('EDIT_ROMCOLLECTION_LAUNCHERS', args)
            return
        
        # >> Execute subcommand. May be atomic, maybe a submenu.
        logger.debug('REMOVE_COLLECTION_LAUNCHER: Selected {}'.format(selected_option.get_id()))
        if not kodi.dialog_yesno(kodi.translate(41059).format(selected_option.get_name())):
            logger.debug('REMOVE_COLLECTION_LAUNCHER: cmd_remove_romcollection_launchers() Cancelled operation.')
            AppMediator.async_cmd('EDIT_ROMCOLLECTION_LAUNCHERS', args)
            return
        
        romcollection_repository.remove_launcher(romcollection.get_id(), selected_option.get_id())
        logger.info(f'Removed launcher#{selected_option.get_id()}')
        uow.commit()
    
    kodi.notify(kodi.translate(41004).format(selected_option.get_name()))
    AppMediator.sync_cmd('EDIT_ROMCOLLECTION_LAUNCHERS', args)

   
@AppMediator.register('REMOVE_SOURCE_LAUNCHER')
def cmd_remove_source_launchers(args):
    source_id: str = args['source_id'] if 'source_id' in args else None
    
    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        source_repository = SourcesRepository(uow)
        source = source_repository.find(source_id)
    
        launchers = source.get_launchers()
        if len(launchers) == 0:
            kodi.notify(kodi.translate(41168))
            AppMediator.sync_cmd('EDIT_SOURCE_LAUNCHERS', args)
            return
        
        options = collections.OrderedDict()
        for launcher in launchers:
            options[launcher] = kodi.get_listitem(launcher.get_name(), launcher.get_addon_name())
        
        s = kodi.translate(41103)
        selected_option: ROMLauncherAddon = kodi.OrdDictionaryDialog().select(s, options, use_details=True)
        
        if selected_option is None:
            # >> Exits context menu
            logger.debug('REMOVE_SOURCE_LAUNCHER: Selected None. Closing context menu')
            AppMediator.sync_cmd('EDIT_SOURCE_LAUNCHERS', args)
            return
        
        logger.debug(f'REMOVE_SOURCE_LAUNCHER: Selected {selected_option.get_id()}')
        if not kodi.dialog_yesno(kodi.translate(41059).format(selected_option.get_name())):
            logger.debug('REMOVE_SOURCE_LAUNCHER: Cancelled operation.')
            AppMediator.async_cmd('EDIT_SOURCE_LAUNCHERS', args)
            return
        
        source_repository.remove_launcher(source.get_id(), selected_option.get_id())
        logger.info(f'Removed launcher#{selected_option.get_id()}')
        uow.commit()
    
    kodi.notify(kodi.translate(41004).format(selected_option.get_name()))
    AppMediator.sync_cmd('EDIT_SOURCE_LAUNCHERS', args)

  
@AppMediator.register('REMOVE_ROM_LAUNCHER')
def cmd_remove_rom_launchers(args):
    rom_id: str = args['rom_id'] if 'rom_id' in args else None
    
    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        repository = ROMsRepository(uow)
        rom = repository.find_rom(rom_id)
    
        launchers = rom.get_launchers()
        if len(launchers) == 0:
            kodi.notify(kodi.translate(41002))
            AppMediator.sync_cmd('EDIT_ROM_LAUNCHERS', args)
            return
        
        options = collections.OrderedDict()
        for launcher in launchers:
            options[launcher] = kodi.get_listitem(launcher.get_name(), launcher.get_addon_name())
        
        s = kodi.translate(41103)
        selected_option: ROMLauncherAddon = kodi.OrdDictionaryDialog().select(s, options, use_details=True)
        
        if selected_option is None:
            # >> Exits context menu
            logger.debug('Selected None. Closing context menu')
            AppMediator.sync_cmd('EDIT_ROM_LAUNCHERS', args)
            return
        
        logger.debug(f'Selected {selected_option.get_id()}')
        if not kodi.dialog_yesno(kodi.translate(41059).format(selected_option.get_name())):
            logger.debug('Cancelled operation.')
            AppMediator.async_cmd('EDIT_ROM_LAUNCHERS', args)
            return
        
        repository.remove_launcher(rom.get_id(), selected_option.get_id())
        logger.info(f'Removed launcher#{selected_option.get_id()}')
        uow.commit()
    
    kodi.notify(kodi.translate(41004).format(selected_option.get_name()))
    AppMediator.sync_cmd('EDIT_ROM_LAUNCHERS', args)

      
@AppMediator.register('SET_DEFAULT_COLLECTION_LAUNCHER')
def cmd_set_default_romcollection_launchers(args):
    romcollection_id: str = args['romcollection_id'] if 'romcollection_id' in args else None
    
    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        romcollection_repository = ROMCollectionRepository(uow)
        romcollection = romcollection_repository.find_romcollection(romcollection_id)
    
        launchers = romcollection.get_launchers()
        if len(launchers) == 0:
            kodi.notify(kodi.translate(41003))
            AppMediator.sync_cmd('EDIT_ROMCOLLECTION_LAUNCHERS', args)
            return
        
        options = collections.OrderedDict()
        for launcher in launchers:
            options[launcher.get_id()] = kodi.get_listitem(launcher.get_name(), launcher.get_addon_name())
        
        s = kodi.translate(41104)
        selected_option = kodi.OrdDictionaryDialog().select(s, options, use_details=True)
        
        if selected_option is None:
            # >> Exits context menu
            logger.debug('SET_DEFAULT_COLLECTION_LAUNCHER: Selected None. Closing context menu')
            AppMediator.sync_cmd('EDIT_ROMCOLLECTION_LAUNCHERS', args)
            return
        
        # >> Execute subcommand. May be atomic, maybe a submenu.
        logger.debug(f'SET_DEFAULT_COLLECTION_LAUNCHER: Selected {selected_option}')
        romcollection.set_launcher_as_default(selected_option)
        romcollection_repository.update_romcollection(romcollection)
        uow.commit()
    
    AppMediator.sync_cmd('EDIT_ROMCOLLECTION_LAUNCHERS', args)

    
@AppMediator.register('SET_DEFAULT_SOURCE_LAUNCHER')
def cmd_set_default_source_launchers(args):
    source_id: str = args['source_id'] if 'source_id' in args else None
    
    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        source_repository = SourcesRepository(uow)
        source = source_repository.find(source_id)

        launchers = source.get_launchers()
        if len(launchers) == 0:
            kodi.notify(kodi.translate(41168))
            AppMediator.sync_cmd('EDIT_SOURCE_LAUNCHERS', args)
            return
        
        options = collections.OrderedDict()
        for launcher in launchers:
            options[launcher.get_id()] = launcher.get_name()
        
        s = kodi.translate(41104)
        selected_option = kodi.OrdDictionaryDialog().select(s, options, use_details=True)
        
        if selected_option is None:
            # >> Exits context menu
            logger.debug('Selected None. Closing context menu')
            AppMediator.sync_cmd('EDIT_SOURCE_LAUNCHERS', args)
            return
        
        # >> Execute subcommand. May be atomic, maybe a submenu.
        logger.debug(f'Selected {selected_option}')
        source.set_launcher_as_default(selected_option)
        source_repository.update_source(source)
        uow.commit()
    
    AppMediator.sync_cmd('EDIT_SOURCE_LAUNCHERS', args)


@AppMediator.register('SET_DEFAULT_ROM_LAUNCHER')
def cmd_set_default_rom_launchers(args):
    rom_id: str = args['rom_id'] if 'rom_id' in args else None
    
    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        repository = ROMsRepository(uow)
        rom = repository.find_rom(rom_id)
    
        launchers = rom.get_launchers()
        if len(launchers) == 0:
            kodi.notify(kodi.translate(41002))
            AppMediator.sync_cmd('EDIT_ROM_LAUNCHERS', args)
            return
        
        options = collections.OrderedDict()
        for launcher in launchers:
            options[launcher.get_id()] = kodi.get_listitem(launcher.get_name(), launcher.get_addon_name())
        
        s = kodi.translate(41104)
        selected_option = kodi.OrdDictionaryDialog().select(s, options, use_details=True)
        
        if selected_option is None:
            # >> Exits context menu
            logger.debug('Selected None. Closing context menu')
            AppMediator.sync_cmd('EDIT_ROM_LAUNCHERS', args)
            return
        
        # >> Execute subcommand. May be atomic, maybe a submenu.
        logger.debug(f'Selected {selected_option}')
        rom.set_launcher_as_default(selected_option)
        repository.update_rom(rom)
        uow.commit()
    
    AppMediator.sync_cmd('EDIT_ROM_LAUNCHERS', args)


# -------------------------------------------------------------------------------------------------
# Random ROM launching
# -------------------------------------------------------------------------------------------------
@AppMediator.register('LAUNCH_RANDOM_ROM')
def cmd_launch_random_rom(args):
    import random

    romcollection_id = args.get('romcollection_id')

    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        rom_repository = ROMsRepository(uow)

        if romcollection_id:
            romcollection_repository = ROMCollectionRepository(uow)
            romcollection = romcollection_repository.find_romcollection(
                romcollection_id
            )

            if romcollection is None:
                logger.warning(
                    f'RANDOM_ROM: ROM collection "{romcollection_id}" '
                    f'was not found.'
                )
                kodi.notify_warn(kodi.translate(44162))
                return

            roms = list(
                rom_repository.find_roms_by_romcollection(
                    romcollection
                )
            )
            rom_ids = [rom.get_id() for rom in roms]

            logger.info(
                f'RANDOM_ROM: Found {len(rom_ids)} game(s) in '
                f'collection "{romcollection.get_name()}".'
            )
        else:
            rom_ids = rom_repository.find_all_rom_ids()

            logger.info(
                f'RANDOM_ROM: Found {len(rom_ids)} game(s) '
                f'in the full library.'
            )

    if not rom_ids:
        logger.warning(
            'RANDOM_ROM: No games are available to launch.'
        )
        kodi.notify_warn(kodi.translate(44162))
        return

    rom_id = random.choice(rom_ids)

    logger.info(
        f'RANDOM_ROM: Selected ROM "{rom_id}"'
        + (
            f' from collection "{romcollection_id}".'
            if romcollection_id
            else ' from the full library.'
        )
    )

    AppMediator.sync_cmd(
        'EXECUTE_ROM',
        {'rom_id': rom_id}
    )


# -------------------------------------------------------------------------------------------------
# ROMCollection Launcher executing
# -------------------------------------------------------------------------------------------------
def _managed_windows_addon_available():
    """Check whether Kodi has the optional managed launcher enabled."""
    try:
        response = kodi.jsonrpc_query(
            'Addons.GetAddons',
            params={
                'installed': True,
                'enabled': True,
                'type': 'xbmc.python.script'
            }
        )
        addons = response.get('result', {}).get('addons', [])
        return any(
            addon.get('addonid') == 'script.akl.managedlauncher'
            for addon in addons
        )
    except Exception:
        logger.exception('Managed Windows Launcher availability check failed')
        return False

def _new_managed_launch_id():
    """Generate a unique identifier for one managed ROM launch."""
    import uuid
    return uuid.uuid4().hex

def _dispatch_managed_launch_stats(managed_stats_args):
    """Request managed bookkeeping without treating dispatch as completion."""
    if not isinstance(managed_stats_args, dict):
        raise ValueError('Managed launch arguments must be a dictionary')

    rom_id = managed_stats_args.get('rom_id')
    launch_id = managed_stats_args.get('launch_id')

    if not isinstance(rom_id, str) or not rom_id:
        raise ValueError('Managed launch requires a ROM ID')

    import re
    if not isinstance(launch_id, str) or not re.fullmatch(
        r'[A-Za-z0-9_-]{1,128}', launch_id
    ):
        raise ValueError('Managed launch requires a valid launch ID')

    AppMediator.async_cmd(
        'MANAGED_ROM_WAS_LAUNCHED',
        {
            'rom_id': rom_id,
            'launch_id': launch_id
        }
    )

def _dispatch_launch_stats(managed_enabled, managed_stats_args, legacy_args):
    """Dispatch exactly one statistics command for a launched ROM."""
    if managed_enabled:
        _dispatch_managed_launch_stats(managed_stats_args)
    else:
        AppMediator.async_cmd('ROM_WAS_LAUNCHED', legacy_args)

@AppMediator.register('EXECUTE_ROM')
def cmd_execute_rom_with_launcher(args):
    rom_id: str = args['rom_id'] if 'rom_id' in args else None
    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        rom_repository = ROMsRepository(uow)
        romcollection_repository = ROMCollectionRepository(uow)
        source_repository = SourcesRepository(uow)
        addon_repository = AklAddonRepository(uow)

        rom = rom_repository.find_rom(rom_id)
        logger.info(f'Executing ROM {rom.get_name()}')
        
        romcollections = romcollection_repository.find_romcollections_by_rom(rom.get_id())
        source = source_repository.find(rom.get_scanned_by())
        launchers = rom.get_launchers()
        if launchers is None:
            launchers = []
        
        if source:
            launchers.extend(source.get_launchers())
        
        for romcollection in romcollections:
            launchers.extend(romcollection.get_launchers())
        
        if len(launchers) == 0:
            is_standalone_src = rom.get_scanned_data_element("standalone")
            file_path = rom.get_scanned_data_element("file")
            
            standalone_launchable = is_standalone_src and int(is_standalone_src) == 1
            
            if not standalone_launchable or not file_path:
                logger.warning(f'No launcher configured for ROM {rom.get_name()}')
                
            if not standalone_launchable and settings.getSettingAsBool('fallback_to_retroplayer'):
                logger.info('Automatic fallback to Retroplayer as launcher applied.')
                retroplayer_addon = addon_repository.find_by_addon_id(constants.RETROPLAYER_LAUNCHER_APP_NAME, constants.AddonType.LAUNCHER)
                retroplayer_launcher = ROMLauncherAddonFactory.create(retroplayer_addon, {})
                launchers.append(retroplayer_launcher)
            
            if file_path:
                addon_id = "script.akl.defaults"
                addon = addon_repository.find_by_addon_id(addon_id, constants.AddonType.LAUNCHER)
                launcher = ROMLauncherAddonFactory.create(addon, None)
                launcher.set_settings({"name": f"Standalone File Launcher: {file_path}"})
                launcher.set_id("STANDALONE")
                launchers.append(launcher)
                            
            if len(launchers) == 0:
                kodi.notify_warn(kodi.translate(41001))
                return
            
    selected_launcher = launchers[0]
    if len(launchers) > 1:
        launcher_options = collections.OrderedDict()
        preselected = None
        for launcher in launchers:
            launcher_options[launcher] = launcher.get_name()
            if launcher.is_default():
                preselected = launcher
        dialog = kodi.OrdDictionaryDialog()
        selected_launcher = dialog.select(kodi.translate(41105), launcher_options, preselect=preselected)

    if selected_launcher is None:
        return
    
    # Managed Windows launch diagnostic (no behavior change).
    selected_addon_id = selected_launcher.get_addon().get_addon_id()
    managed_requested = (
        selected_addon_id == 'script.akl.managedlauncher'
        or (
            selected_addon_id == 'script.akl.defaults'
            and selected_launcher.get_setting('managed_windows_launch', False) is True
        )
    )
    managed_enabled = (
        managed_requested and _managed_windows_addon_available()
    )

    # Steam uses its own App ID resolver and requires a dedicated managed
    # execution path. Detect opt-in now, but do not activate it until ready.
    steam_managed_requested = (
        selected_addon_id == 'script.akl.steam'
        and selected_launcher.get_setting('managed_windows_launch', False) is True
    )
    steam_managed_enabled = (
        steam_managed_requested and _managed_windows_addon_available()
    )
    if steam_managed_requested and not steam_managed_enabled:
        logger.warning(
            'Managed Steam Launch requested but managed helper is unavailable'
        )
    logger.info(
        'Managed Windows Launch diagnostic: enabled=%s, launcher=%s',
        managed_enabled,
        selected_launcher.get_name()
    )
    # Generate a fresh ID only for opted-in managed launches.
    managed_launch_id = None
    if managed_enabled or steam_managed_enabled:
        managed_launch_id = _new_managed_launch_id()
        logger.info(
            'Managed Windows Launch prepared: launch_id=%s, rom_id=%s',
            managed_launch_id,
            rom_id
        )

    # Prepare managed bookkeeping arguments without dispatching them yet.
    managed_stats_args = None
    if managed_launch_id is not None:
        managed_stats_args = {
            'rom_id': rom_id,
            'launch_id': managed_launch_id
        }

    # Preserve existing behavior for non-managed launchers. Managed Windows
    # launches can disable returning to the last viewed AKL collection.
    queue_collection_return = True
    if managed_enabled or steam_managed_enabled:
        try:
            managed_addon = xbmcaddon.Addon(
                'script.akl.managedlauncher'
            )
            queue_collection_return = managed_addon.getSettingBool(
                'return_to_last_collection'
            )
        except Exception:
            logger.exception(
                'Managed collection return: unable to read setting; '
                'preserving default enabled behavior'
            )
            queue_collection_return = True

    # Request a one-time return to the last viewed AKL collection.
    try:
        addon_data = xbmcvfs.translatePath(
            'special://profile/addon_data/plugin.program.akl/'
        )

        last_collection_file = os.path.join(
            addon_data, 'last_viewed_collection.txt'
        )
        return_file = os.path.join(
            addon_data, 'pending_collection_return.txt'
        )

        if not queue_collection_return:
            if os.path.isfile(return_file):
                os.remove(return_file)
            logger.info(
                'Managed collection return: disabled; Kodi will open normally'
            )
        elif os.path.isfile(last_collection_file):
            with open(last_collection_file, 'r', encoding='utf-8') as handle:
                collection_url = handle.read().strip()

            if re.fullmatch(
                r'plugin://plugin\.program\.akl/collection/[A-Za-z0-9_-]+/?',
                collection_url
            ):
                with open(return_file, 'w', encoding='utf-8') as handle:
                    handle.write(collection_url)

                logger.info(
                    'AKL collection return: pending %s', collection_url
                )
            else:
                logger.warning(
                    'AKL collection return: invalid URL %s', collection_url
                )
        else:
            logger.info('AKL collection return: no tracked collection')
    except Exception:
        logger.exception('AKL collection return: unable to queue return')
    if managed_enabled:
        launch_command = selected_launcher.get_launch_command(rom)
        launch_command['--managed_launch_id'] = managed_launch_id
        kodi.run_script(
            'script.akl.managedlauncher',
            launch_command
        )
    elif steam_managed_enabled:
        launch_command = selected_launcher.get_launch_command(rom)
        launch_command['--managed_launch_id'] = managed_launch_id
        kodi.run_script(
            'script.akl.steam',
            launch_command
        )
    else:
        selected_launcher.launch(rom)

    if not steam_managed_enabled:
        _dispatch_launch_stats(managed_enabled, managed_stats_args, args)
