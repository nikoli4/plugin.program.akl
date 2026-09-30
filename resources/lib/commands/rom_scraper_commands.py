# -*- coding: utf-8 -*-
#
# Advanced Kodi Launcher: Commands (ROM scraper management)
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
import typing
import json

from akl import constants
from akl.utils import kodi, io
from akl.scrapers import ScraperSettings

from resources.lib.commands.mediator import AppMediator
from resources.lib import globals
from resources.lib.repositories import UnitOfWork, AklAddonRepository, ROMsRepository
from resources.lib.repositories import ROMCollectionRepository, SourcesRepository
from resources.lib.domain import AssetPath, ScraperAddon, g_assetFactory

logger = logging.getLogger(__name__)


SCRAPE_ROMS = 'SCRAPE_ROMS'
SCRAPE_ROMS_WITH_SETTINGS = 'SCRAPE_ROMS_WITH_SETTINGS'
SCRAPE_SYSTEM = 'SCRAPE_SYSTEM'
SCRAPE_SYSTEM_WITH_SETTINGS = 'SCRAPE_SYSTEM_WITH_SETTINGS'
PREPARE_WIZARD_GAME_SCRAPE = 'PREPARE_WIZARD_GAME_SCRAPE'
PREPARE_WIZARD_SYSTEM_SCRAPE = 'PREPARE_WIZARD_SYSTEM_SCRAPE'
SCRAPE_PREPARED_WIZARD_GAMES = 'SCRAPE_PREPARED_WIZARD_GAMES'

@AppMediator.register(SCRAPE_SYSTEM)
def cmd_scrape_system(args):
    romcollection_id: str = (
        args['romcollection_id']
        if 'romcollection_id' in args
        else None
    )

    logger.info(
        f'SYSTEM_SCRAPE: Preparing system scrape for collection '
        f'"{romcollection_id}".'
    )

    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        collection_repository = ROMCollectionRepository(uow)
        source_repository = SourcesRepository(uow)

        collection = collection_repository.find_romcollection(
            romcollection_id
        )

        if collection is None:
            logger.error(
                f'SYSTEM_SCRAPE: Collection "{romcollection_id}" '
                f'was not found.'
            )
            return

        rulesets = [
            *collection_repository.find_import_rules_by_collection(
                collection
            )
        ]

        source_ids = []
        for ruleset in rulesets:
            source_id = ruleset.get_source_id()

            if source_id and source_id not in source_ids:
                source_ids.append(source_id)

        if len(source_ids) == 0:
            logger.error(
                f'SYSTEM_SCRAPE: Collection "{collection.get_name()}" '
                f'has no associated source.'
            )
            return

        if len(source_ids) > 1:
            logger.error(
                f'SYSTEM_SCRAPE: Collection "{collection.get_name()}" '
                f'has multiple associated sources. Cannot determine '
                f'system artwork destination automatically.'
            )
            return

        source = source_repository.find(source_ids[0])

        if source is None:
            logger.error(
                f'SYSTEM_SCRAPE: Source "{source_ids[0]}" '
                f'was not found.'
            )
            return

        assets_root = source.get_assets_root_path()

        if assets_root is None:
            logger.error(
                f'SYSTEM_SCRAPE: Source "{source.get_name()}" '
                f'has no artwork root.'
            )
            return

        artwork_root = io.FileName(
            assets_root.getPath().rstrip('/\\')
        ).getDirAsFileName()

        artwork_root.set_isdir(True)

        systems_root = artwork_root.pjoin(
            'Systems',
            isdir=True
        )

        if not systems_root.exists():
            systems_root.makedirs()

        logger.info(
            f'SYSTEM_SCRAPE: Collection="{collection.get_name()}" '
            f'Platform="{collection.get_platform()}" '
            f'Source="{source.get_name()}" '
            f'AssetsRoot="{assets_root.getPath()}".'
        )

        logger.info(
            f'SYSTEM_SCRAPE: ArtworkRoot="'
            f'{artwork_root.getPath()}".'
        )

        logger.info(
            f'SYSTEM_SCRAPE: SystemsRoot="'
            f'{systems_root.getPath()}".'
        )

        system_asset_paths = {}

        for asset_id in collection.get_asset_ids_list():
            asset_info = g_assetFactory.get_asset_info(
                asset_id
            )

            system_asset_path = systems_root.pjoin(
                asset_info.plural.lower(),
                isdir=True
            )

            if not system_asset_path.exists():
                system_asset_path.makedirs()

            system_asset_paths[asset_id] = (
                system_asset_path.getPath()
            )

            logger.info(
                f'SYSTEM_SCRAPE: System asset destination '
                f'{asset_id}="'
                f'{system_asset_path.getPath()}".'
            )

        prepared_scraper_settings = args.get(
            'prepared_scraper_settings'
        )

        if prepared_scraper_settings:
            scraper_settings = ScraperSettings.from_settings_dict(
                prepared_scraper_settings
            )

            logger.info(
                'SETUP_WIZARD: Restored prepared system scrape settings.'
            )
        else:
            scraper_settings = ScraperSettings.from_addon_settings()

        prepared_scraper_id = args.get(
            'prepared_scraper_id'
        )

        if prepared_scraper_id:
            addon_repository = AklAddonRepository(uow)
            addon = addon_repository.find(
                prepared_scraper_id
            )

            if addon is None:
                logger.error(
                    f'SYSTEM_SCRAPE: Prepared scraper '
                    f'"{prepared_scraper_id}" was not found.'
                )
                return

            selected_addon = ScraperAddon(
                addon,
                scraper_settings
            )

            logger.info(
                f'SETUP_WIZARD: Using prepared system scraper '
                f'"{selected_addon.get_name()}" for collection '
                f'"{romcollection_id}".'
            )
        else:
            dialog_title = 'Select System Scraper'
            selected_addon = _select_scraper(
                uow,
                dialog_title,
                scraper_settings
            )

        if selected_addon is None:
            logger.info(
                'SYSTEM_SCRAPE: System scrape cancelled.'
            )

            setup_wizard_collection_id = kodi.get_windowprop(
                'AKL.SetupWizard.SystemScrapeCollectionID'
            )

            if setup_wizard_collection_id == romcollection_id:
                kodi.clear_windowprops([
                    'AKL.SetupWizard.SystemScrapeCollectionID'
                ])

                logger.info(
                    f'SETUP_WIZARD: Cleared system scrape continuation '
                    f'marker after cancellation for collection '
                    f'"{romcollection_id}".'
                )

            return

        if not prepared_scraper_settings:
            scraper_settings.asset_IDs_to_scrape = (
                selected_addon.get_supported_assets()
            )
            scraper_settings.metadata_IDs_to_scrape = (
                selected_addon.get_supported_metadata()
            )

            args['scraper_settings'] = scraper_settings
            args['scraper_id'] = selected_addon.addon.get_id()
            args['scraper_supported_metadata'] = (
                selected_addon.get_supported_metadata()
            )
            args['scraper_supported_assets'] = (
                selected_addon.get_supported_assets()
            )

            AppMediator.sync_cmd(
                SCRAPE_SYSTEM_WITH_SETTINGS,
                args
            )
            return

        selected_addon.set_scraper_settings(
            scraper_settings
        )

        logger.info(
            f'SYSTEM_SCRAPE: Starting scraper '
            f'"{selected_addon.get_name()}" for '
            f'"{collection.get_name()}".'
        )

        selected_addon.scrape_system(
            collection,
            collection.get_platform(),
            collection.get_name(),
            system_asset_paths
        )

@AppMediator.register(SCRAPE_SYSTEM_WITH_SETTINGS)
def cmd_scrape_system_with_settings(args):
    romcollection_id: str = args.get('romcollection_id')
    scraper_id: str = args.get('scraper_id')
    scraper_settings: ScraperSettings = args.get(
        'scraper_settings',
        ScraperSettings.from_addon_settings()
    )

    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        addon_repository = AklAddonRepository(uow)
        collection_repository = ROMCollectionRepository(uow)

        collection = collection_repository.find_romcollection(
            romcollection_id
        )
        addon = addon_repository.find(scraper_id)

        if collection is None or addon is None:
            logger.error(
                f'SYSTEM_SCRAPE: Unable to configure system scrape for '
                f'collection "{romcollection_id}".'
            )
            return

        selected_addon = ScraperAddon(
            addon,
            scraper_settings
        )

        assets_to_scrape = g_assetFactory.get_asset_list_by_IDs(
            scraper_settings.asset_IDs_to_scrape
        )
        metadata_to_scrape = [
            constants.METADATA_DESCRIPTIONS[meta_id]
            for meta_id in scraper_settings.metadata_IDs_to_scrape
        ]

        options = collections.OrderedDict()

        options['SCRAPER_METADATA_POLICY'] = (
            kodi.translate(41115).format(
                kodi.translate(scraper_settings.scrape_metadata_policy)
            )
        )
        options['SCRAPER_ASSET_POLICY'] = (
            kodi.translate(41116).format(
                kodi.translate(scraper_settings.scrape_assets_policy)
            )
        )
        options['SCRAPER_SEARCH_TERM_MODE'] = (
            kodi.translate(41117).format(
                kodi.translate(scraper_settings.search_term_mode)
            )
        )
        options['SCRAPER_GAME_SELECTION_MODE'] = (
            kodi.translate(41118).format(
                kodi.translate(scraper_settings.game_selection_mode)
            )
        )
        options['SCRAPER_ASSET_SELECTION_MODE'] = (
            kodi.translate(41119).format(
                kodi.translate(scraper_settings.asset_selection_mode)
            )
        )
        options['SCRAPER_META_TO_SCRAPE'] = (
            kodi.translate(42030).format(
                ', '.join(metadata_to_scrape)
            )
        )
        options['SCRAPER_ASSETS_TO_SCRAPE'] = (
            kodi.translate(42031).format(
                ', '.join([a.plural for a in assets_to_scrape])
            )
        )
        options['SCRAPER_OVERWRITE_META_MODE'] = (
            kodi.translate(42032).format(
                kodi.translate(42035)
                if scraper_settings.overwrite_existing_meta
                else kodi.translate(42036)
            )
        )
        options['SCRAPER_OVERWRITE_ASSETS_MODE'] = (
            kodi.translate(42033).format(
                kodi.translate(42035)
                if scraper_settings.overwrite_existing_assets
                else kodi.translate(42036)
            )
        )
        options['SCRAPE'] = kodi.translate(40881)

        dialog_title = (
            f'Scrape System - {collection.get_name()} '
            f'({selected_addon.get_name()})'
        )

        selected_option = kodi.OrdDictionaryDialog().select(
            dialog_title,
            options,
            preselect='SCRAPE'
        )

        if selected_option is None:
            logger.info(
                'SYSTEM_SCRAPE: System scrape settings cancelled.'
            )
            return

        if selected_option != 'SCRAPE':
            args['ret_cmd'] = SCRAPE_SYSTEM_WITH_SETTINGS
            AppMediator.sync_cmd(
                selected_option,
                args
            )
            return

    # Re-enter SCRAPE_SYSTEM as a prepared operation so it executes rather
    # than reopening the manual settings screen.
    args['prepared_scraper_id'] = scraper_id
    args['prepared_scraper_settings'] = (
        scraper_settings.get_data_dic()
    )

    AppMediator.sync_cmd(
        SCRAPE_SYSTEM,
        args
    )

@AppMediator.register(PREPARE_WIZARD_SYSTEM_SCRAPE)
def cmd_prepare_wizard_system_scrape(args):
    romcollection_id = args.get('romcollection_id')

    logger.info(
        f'SETUP_WIZARD: Preparing system scrape settings for '
        f'collection "{romcollection_id}".'
    )

    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        collection_repository = ROMCollectionRepository(uow)

        collection = collection_repository.find_romcollection(
            romcollection_id
        )

        if collection is None:
            logger.error(
                f'SETUP_WIZARD: Collection "{romcollection_id}" '
                f'was not found while preparing system scraping.'
            )
            return

        scraper_settings = ScraperSettings.from_addon_settings()

        shared_system_scraper_id = kodi.get_windowprop(
            'AKL.SetupWizard.SystemScraperID'
        )
        reuse_scraper_providers = kodi.get_windowprop(
            'AKL.SetupWizard.ReuseScraperProviders'
        )

        if (
            shared_system_scraper_id
            and reuse_scraper_providers == 'true'
        ):
            addon_repository = AklAddonRepository(uow)
            addon = addon_repository.find(
                shared_system_scraper_id
            )

            if addon is None:
                logger.error(
                    f'SETUP_WIZARD: Shared system scraper '
                    f'"{shared_system_scraper_id}" could not be found.'
                )
                return

            selected_addon = ScraperAddon(
                addon,
                scraper_settings
            )

            logger.info(
                f'SETUP_WIZARD: Reusing shared system scraper provider '
                f'"{selected_addon.get_name()}" for '
                f'"{collection.get_name()}".'
            )
        else:
            dialog_title = (
                f'Select System Scraper - {collection.get_name()}'
            )

            selected_addon = _select_scraper(
                uow,
                dialog_title,
                scraper_settings
            )

            if selected_addon is None:
                logger.info(
                    'SETUP_WIZARD: System scraper preparation cancelled.'
                )
                return

            if not shared_system_scraper_id:
                kodi.set_windowprop(
                    'AKL.SetupWizard.SystemScraperID',
                    selected_addon.addon.get_id()
                )

                logger.info(
                    f'SETUP_WIZARD: Saved shared system scraper provider '
                    f'"{selected_addon.get_name()}" for this setup batch.'
                )

        shared_system_settings_json = kodi.get_windowprop(
            'AKL.SetupWizard.SystemScrapeSettings'
        )

        scrape_queue_json = kodi.get_windowprop(
            'AKL.SetupWizard.ScrapeQueue'
        )

        try:
            scrape_queue = (
                json.loads(scrape_queue_json)
                if scrape_queue_json
                else []
            )
        except (TypeError, ValueError):
            logger.warning(
                'SETUP_WIZARD: Invalid scrape queue while advancing '
                'scrape preparation.'
            )
            scrape_queue = []

        reuse_scrape_settings = kodi.get_windowprop(
            'AKL.SetupWizard.ReuseScrapeSettings'
        )

        reuse_shared_settings = (
            reuse_scrape_settings == 'true'
        )

        if shared_system_settings_json and reuse_shared_settings:
            try:
                scraper_settings = ScraperSettings.from_settings_dict(
                    json.loads(shared_system_settings_json)
                )

                logger.info(
                    'SETUP_WIZARD: Reusing shared system scrape '
                    'settings for this setup batch.'
                )
            except (TypeError, ValueError):
                logger.warning(
                    'SETUP_WIZARD: Shared system scrape settings '
                    'were invalid. Configuring them again.'
                )
                shared_system_settings_json = ''
                scraper_settings = ScraperSettings.from_addon_settings()

        scraper_settings.asset_IDs_to_scrape = (
            selected_addon.get_supported_assets()
        )
        scraper_settings.metadata_IDs_to_scrape = (
            selected_addon.get_supported_metadata()
        )

        if not (
            shared_system_settings_json
            and reuse_shared_settings
        ):
            system_options = collections.OrderedDict()

            system_options['OVERWRITE_META'] = (
                kodi.translate(44129).format(
                    kodi.translate(44131)
                    if scraper_settings.overwrite_existing_meta
                    else kodi.translate(44132)
                )
            )

            system_options['OVERWRITE_ASSETS'] = (
                kodi.translate(44130).format(
                    kodi.translate(44131)
                    if scraper_settings.overwrite_existing_assets
                    else kodi.translate(44132)
                )
            )

            system_options['SAVE'] = kodi.translate(44133)

            while True:
                selected_system_option = (
                    kodi.OrdDictionaryDialog().select(
                        kodi.translate(44134).format(
                            collection.get_name()
                        ),
                        system_options,
                        preselect='SAVE'
                    )
                )

                if selected_system_option is None:
                    logger.info(
                        'SETUP_WIZARD: System scrape settings '
                        'cancelled.'
                    )
                    return

                if selected_system_option == 'OVERWRITE_META':
                    scraper_settings.overwrite_existing_meta = (
                        not scraper_settings.overwrite_existing_meta
                    )

                    system_options['OVERWRITE_META'] = (
                        kodi.translate(44129).format(
                            kodi.translate(44131)
                            if scraper_settings.overwrite_existing_meta
                            else kodi.translate(44132)
                        )
                    )
                    continue

                if selected_system_option == 'OVERWRITE_ASSETS':
                    scraper_settings.overwrite_existing_assets = (
                        not scraper_settings.overwrite_existing_assets
                    )

                    system_options['OVERWRITE_ASSETS'] = (
                        kodi.translate(44130).format(
                            kodi.translate(44131)
                            if scraper_settings.overwrite_existing_assets
                            else kodi.translate(44132)
                        )
                    )
                    continue

                if selected_system_option == 'SAVE':
                    break

            kodi.set_windowprop(
                'AKL.SetupWizard.SystemScrapeSettings',
                json.dumps(scraper_settings.get_data_dic())
            )

            logger.info(
                'SETUP_WIZARD: Saved shared system scrape settings '
                'for this setup batch.'
            )

        prepared_scrapes_json = kodi.get_windowprop(
            'AKL.SetupWizard.PreparedScrapes'
        )

        try:
            prepared_scrapes = (
                json.loads(prepared_scrapes_json)
                if prepared_scrapes_json
                else {}
            )
        except (TypeError, ValueError):
            logger.warning(
                'SETUP_WIZARD: Invalid prepared scrape data found. '
                'Starting new prepared scrape data.'
            )
            prepared_scrapes = {}

        if romcollection_id not in prepared_scrapes:
            prepared_scrapes[romcollection_id] = {}

        prepared_scrapes[romcollection_id][
            'system_scraper_id'
        ] = selected_addon.addon.get_id()

        prepared_scrapes[romcollection_id][
            'system_scraper_settings'
        ] = scraper_settings.get_data_dic()

        kodi.set_windowprop(
            'AKL.SetupWizard.PreparedScrapes',
            json.dumps(prepared_scrapes)
        )

        logger.info(
            f'SETUP_WIZARD: Saved prepared system scraper '
            f'"{selected_addon.get_name()}" for collection '
            f'"{romcollection_id}".'
        )

        logger.info(
            f'SETUP_WIZARD: Continuing to game scrape preparation '
            f'for collection "{romcollection_id}".'
        )

        AppMediator.async_cmd(
            PREPARE_WIZARD_GAME_SCRAPE,
            {'romcollection_id': romcollection_id}
        )

# -------------------------------------------------------------------------------------------------
# Start scraping
# -------------------------------------------------------------------------------------------------
@AppMediator.register(SCRAPE_ROMS)
def cmd_scrape_romcollection(args):
    romcollection_id: str = args['romcollection_id'] if 'romcollection_id' in args else None

    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        collection_repository = ROMCollectionRepository(uow)
        collection = collection_repository.find_romcollection(romcollection_id)

        scraper_settings: ScraperSettings = ScraperSettings.from_addon_settings()

        dialog_title = kodi.translate(41124).format(collection.get_name())
        selected_addon = _select_scraper(uow, dialog_title, scraper_settings)
        if selected_addon is None:
            # >> Exits context menu
            logger.debug(
                'SCRAPE_ROMS: cmd_scrape_romcollection() '
                'Selected None. Closing context menu'
            )

            setup_wizard_collection_id = kodi.get_windowprop(
                'AKL.SetupWizard.GameScrapeCollectionID'
            )

            if setup_wizard_collection_id == romcollection_id:
                kodi.clear_windowprops([
                    'AKL.SetupWizard.GameScrapeCollectionID'
                ])

                logger.info(
                    f'SETUP_WIZARD: Cleared game scrape continuation '
                    f'marker after cancellation for collection '
                    f'"{romcollection_id}".'
                )

                return

            AppMediator.sync_cmd(
                'ROMCOLLECTION_MANAGE_ROMS',
                args
            )
            return

        scraper_settings.asset_IDs_to_scrape = selected_addon.get_supported_assets()
        scraper_settings.metadata_IDs_to_scrape = selected_addon.get_supported_metadata()

        logger.debug(f'cmd_scrape_romcollection() Selected scraper#{selected_addon.get_name()}')
        args['scraper_settings'] = scraper_settings
        args['scraper_id'] = selected_addon.addon.get_id()
        args['scraper_supported_metadata'] = selected_addon.get_supported_metadata()
        args['scraper_supported_assets'] = selected_addon.get_supported_assets()

    AppMediator.sync_cmd(SCRAPE_ROMS_WITH_SETTINGS, args)


@AppMediator.register('SCRAPE_SOURCE_ROMS')
def cmd_scrape_source(args):
    source_id: str = args['source_id'] if 'source_id' in args else None

    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        source_repository = SourcesRepository(uow)
        source = source_repository.find(source_id)

        scraper_settings: ScraperSettings = ScraperSettings.from_addon_settings()

        dialog_title = kodi.translate(41110).format(source.get_name())
        selected_addon = _select_scraper(uow, dialog_title, scraper_settings)
        if selected_addon is None:
            # >> Exits context menu
            logger.debug('SCRAPE_SOURCE_ROMS: cmd_scrape_source() Selected None. Closing context menu')
            AppMediator.sync_cmd('SOURCE_MANAGE_ROMS', args)
            return

        scraper_settings.asset_IDs_to_scrape = selected_addon.get_supported_assets()
        scraper_settings.metadata_IDs_to_scrape = selected_addon.get_supported_metadata()

        logger.debug(f'cmd_scrape_source() Selected scraper#{selected_addon.get_name()}')
        args['scraper_settings'] = scraper_settings
        args['scraper_id'] = selected_addon.addon.get_id()
        args['scraper_supported_metadata'] = selected_addon.get_supported_metadata()
        args['scraper_supported_assets'] = selected_addon.get_supported_assets()

    AppMediator.sync_cmd(SCRAPE_ROMS_WITH_SETTINGS, args)


# Scrape ROM - Select scraper to use
@AppMediator.register('SCRAPE_ROM')
def cmd_scrape_rom(args):
    rom_id: str = args['rom_id'] if 'rom_id' in args else None

    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        roms_repository = ROMsRepository(uow)
        rom = roms_repository.find_rom(rom_id)

        scraper_settings: ScraperSettings = ScraperSettings.from_addon_settings()

        dialog_title = kodi.translate(41123).format(rom.get_name())
        selected_addon = _select_scraper(uow, dialog_title, scraper_settings)
        if selected_addon is None:
            # >> Exits context menu
            logger.debug('SCRAPE_ROM: Selected None. Closing context menu')
            AppMediator.sync_cmd('EDIT_ROM', args)
            return

        scraper_settings.asset_IDs_to_scrape = selected_addon.get_supported_assets()
        scraper_settings.metadata_IDs_to_scrape = selected_addon.get_supported_metadata()

        logger.debug(f'Selected scraper#{selected_addon.get_addon_name()}')
        args['scraper_settings'] = scraper_settings
        args['scraper_id'] = selected_addon.addon.get_id()
        args['scraper_supported_metadata'] = selected_addon.get_supported_metadata()
        args['scraper_supported_assets'] = selected_addon.get_supported_assets()

    AppMediator.sync_cmd('SCRAPE_ROM_WITH_SETTINGS', args)

@AppMediator.register(PREPARE_WIZARD_GAME_SCRAPE)
def cmd_prepare_wizard_game_scrape(args):
    romcollection_id = args.get('romcollection_id')

    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        collection_repository = ROMCollectionRepository(uow)
        addon_repository = AklAddonRepository(uow)

        collection = collection_repository.find_romcollection(
            romcollection_id
        )

        if collection is None:
            logger.error(
                f'SETUP_WIZARD: Collection "{romcollection_id}" '
                f'was not found while preparing game scraping.'
            )
            return

        scraper_settings = args.get('scraper_settings')

        shared_game_settings_json = kodi.get_windowprop(
            'AKL.SetupWizard.GameScrapeSettings'
        )
        reuse_scrape_settings = kodi.get_windowprop(
            'AKL.SetupWizard.ReuseScrapeSettings'
        )

        reuse_shared_settings = (
            reuse_scrape_settings == 'true'
        )

        if scraper_settings is None:
            if shared_game_settings_json and reuse_shared_settings:
                try:
                    scraper_settings = (
                        ScraperSettings.from_settings_dict(
                            json.loads(shared_game_settings_json)
                        )
                    )

                    logger.info(
                        'SETUP_WIZARD: Reusing shared game scrape '
                        'settings for this setup batch.'
                    )
                except (TypeError, ValueError):
                    logger.warning(
                        'SETUP_WIZARD: Shared game scrape settings '
                        'were invalid. Using addon defaults.'
                    )
                    shared_game_settings_json = ''
                    scraper_settings = (
                        ScraperSettings.from_addon_settings()
                    )
            else:
                scraper_settings = ScraperSettings.from_addon_settings()

            shared_game_scraper_id = kodi.get_windowprop(
                'AKL.SetupWizard.GameScraperID'
            )
            reuse_scraper_providers = kodi.get_windowprop(
                'AKL.SetupWizard.ReuseScraperProviders'
            )

            if (
                shared_game_scraper_id
                and reuse_scraper_providers == 'true'
            ):
                addon = addon_repository.find(
                    shared_game_scraper_id
                )

                if addon is None:
                    logger.error(
                        f'SETUP_WIZARD: Shared game scraper '
                        f'"{shared_game_scraper_id}" could not be found.'
                    )
                    return

                selected_addon = ScraperAddon(
                    addon,
                    scraper_settings
                )

                logger.info(
                    f'SETUP_WIZARD: Reusing shared game scraper provider '
                    f'"{selected_addon.get_name()}" for '
                    f'"{collection.get_name()}".'
                )
            else:
                dialog_title = (
                    f'Select Game Scraper - {collection.get_name()}'
                )

                selected_addon = _select_scraper(
                    uow,
                    dialog_title,
                    scraper_settings
                )

                if selected_addon is None:
                    logger.info(
                        'SETUP_WIZARD: Game scraper preparation cancelled.'
                    )
                    return

                if not shared_game_scraper_id:
                    kodi.set_windowprop(
                        'AKL.SetupWizard.GameScraperID',
                        selected_addon.addon.get_id()
                    )

                    logger.info(
                        f'SETUP_WIZARD: Saved shared game scraper provider '
                        f'"{selected_addon.get_name()}" for this setup batch.'
                    )

            supported_assets = selected_addon.get_supported_assets()
            supported_metadata = selected_addon.get_supported_metadata()

            if shared_game_settings_json and reuse_shared_settings:
                scraper_settings.asset_IDs_to_scrape = [
                    asset_id
                    for asset_id in scraper_settings.asset_IDs_to_scrape
                    if asset_id in supported_assets
                ]

                scraper_settings.metadata_IDs_to_scrape = [
                    metadata_id
                    for metadata_id
                    in scraper_settings.metadata_IDs_to_scrape
                    if metadata_id in supported_metadata
                ]
            else:
                scraper_settings.asset_IDs_to_scrape = supported_assets
                scraper_settings.metadata_IDs_to_scrape = supported_metadata

            args['scraper_settings'] = scraper_settings
            args['scraper_id'] = selected_addon.addon.get_id()
            args['scraper_supported_metadata'] = (
                selected_addon.get_supported_metadata()
            )
            args['scraper_supported_assets'] = (
                selected_addon.get_supported_assets()
            )
        else:
            addon = addon_repository.find(
                args.get('scraper_id')
            )

            if addon is None:
                logger.error(
                    'SETUP_WIZARD: Prepared game scraper '
                    'could not be found.'
                )
                return

            selected_addon = ScraperAddon(
                addon,
                scraper_settings
            )

        assets_to_scrape = (
            g_assetFactory.get_asset_list_by_IDs(
                scraper_settings.asset_IDs_to_scrape
            )
        )

        metadata_to_scrape = [
            constants.METADATA_DESCRIPTIONS[metadata_id]
            for metadata_id
            in scraper_settings.metadata_IDs_to_scrape
        ]

        options = collections.OrderedDict()

        options['SCRAPER_METADATA_POLICY'] = (
            kodi.translate(41115).format(
                kodi.translate(
                    scraper_settings.scrape_metadata_policy
                )
            )
        )
        options['SCRAPER_ASSET_POLICY'] = (
            kodi.translate(41116).format(
                kodi.translate(
                    scraper_settings.scrape_assets_policy
                )
            )
        )
        options['SCRAPER_SEARCH_TERM_MODE'] = (
            kodi.translate(41117).format(
                kodi.translate(
                    scraper_settings.search_term_mode
                )
            )
        )
        options['SCRAPER_GAME_SELECTION_MODE'] = (
            kodi.translate(41118).format(
                kodi.translate(
                    scraper_settings.game_selection_mode
                )
            )
        )
        options['SCRAPER_ASSET_SELECTION_MODE'] = (
            kodi.translate(41119).format(
                kodi.translate(
                    scraper_settings.asset_selection_mode
                )
            )
        )
        options['SCRAPER_META_TO_SCRAPE'] = (
            kodi.translate(42030).format(
                ', '.join(metadata_to_scrape)
            )
        )
        options['SCRAPER_ASSETS_TO_SCRAPE'] = (
            kodi.translate(42031).format(
                ', '.join([
                    asset.plural
                    for asset in assets_to_scrape
                ])
            )
        )
        options['SCRAPER_OVERWRITE_META_MODE'] = (
            kodi.translate(42032).format(
                kodi.translate(
                    42035
                    if scraper_settings.overwrite_existing_meta
                    else 42036
                )
            )
        )
        options['SCRAPER_OVERWRITE_ASSETS_MODE'] = (
            kodi.translate(42033).format(
                kodi.translate(
                    42035
                    if scraper_settings.overwrite_existing_assets
                    else 42036
                )
            )
        )
        options['SCRAPER_IGNORE_TITLES_MODE'] = (
            kodi.translate(42034).format(
                kodi.translate(
                    42035
                    if scraper_settings.ignore_scrap_title
                    else 42036
                )
            )
        )

        options['SAVE'] = 'Save Settings'

        dialog_title = (
            f'Game Scrape Settings - '
            f'{collection.get_name()} - '
            f'{selected_addon.get_name()}'
        )

        if shared_game_settings_json and reuse_shared_settings:
            logger.info(
                'SETUP_WIZARD: Reusing shared game scrape settings '
                f'for "{collection.get_name()}"; skipping settings dialog.'
            )
            selected_option = 'SAVE'
        else:
            selected_option = kodi.OrdDictionaryDialog().select(
                dialog_title,
                options,
                preselect='SAVE'
            )

            if selected_option is None:
                logger.info(
                    'SETUP_WIZARD: Game scrape settings '
                    'preparation cancelled.'
                )
                return

            if selected_option != 'SAVE':
                args['ret_cmd'] = PREPARE_WIZARD_GAME_SCRAPE
                AppMediator.sync_cmd(
                    selected_option,
                    args
                )
                return

        logger.info(
            f'SETUP_WIZARD: Game scrape settings prepared for '
            f'"{collection.get_name()}" using scraper '
            f'"{selected_addon.get_name()}".'
        )

        prepared_scrapes_json = kodi.get_windowprop(
            'AKL.SetupWizard.PreparedScrapes'
        )

        try:
            prepared_scrapes = (
                json.loads(prepared_scrapes_json)
                if prepared_scrapes_json
                else {}
            )
        except (TypeError, ValueError):
            logger.warning(
                'SETUP_WIZARD: Invalid prepared scrape data found. '
                'Starting new prepared scrape data.'
            )
            prepared_scrapes = {}

        if romcollection_id not in prepared_scrapes:
            prepared_scrapes[romcollection_id] = {}

        prepared_scrapes[romcollection_id][
            'game_scraper_id'
        ] = args.get('scraper_id')

        prepared_scrapes[romcollection_id][
            'game_scraper_settings'
        ] = scraper_settings.get_data_dic()

        kodi.set_windowprop(
            'AKL.SetupWizard.GameScrapeSettings',
            json.dumps(scraper_settings.get_data_dic())
        )

        logger.info(
            'SETUP_WIZARD: Saved shared game scrape settings '
            'for this setup batch.'
        )

        scrape_queue_json = kodi.get_windowprop(
            'AKL.SetupWizard.ScrapeQueue'
        )

        try:
            scrape_queue = (
                json.loads(scrape_queue_json)
                if scrape_queue_json
                else []
            )
        except (TypeError, ValueError):
            logger.warning(
                'SETUP_WIZARD: Invalid scrape queue while advancing '
                'scrape preparation.'
            )
            scrape_queue = []

        reuse_scraper_providers = kodi.get_windowprop(
            'AKL.SetupWizard.ReuseScraperProviders'
        )

        if not reuse_scraper_providers and len(scrape_queue) > 1:
            reuse_providers = kodi.dialog_yesno(
                kodi.translate(44135),
                kodi.translate(44137)
            )

            kodi.set_windowprop(
                'AKL.SetupWizard.ReuseScraperProviders',
                'true' if reuse_providers else 'false'
            )

            logger.info(
                f'SETUP_WIZARD: Reuse scraper providers for batch: '
                f'{reuse_providers}.'
            )

        reuse_scrape_settings = kodi.get_windowprop(
            'AKL.SetupWizard.ReuseScrapeSettings'
        )

        if not reuse_scrape_settings and len(scrape_queue) > 1:
            reuse_settings = kodi.dialog_yesno(
                kodi.translate(44136),
                kodi.translate(44137)
            )

            kodi.set_windowprop(
                'AKL.SetupWizard.ReuseScrapeSettings',
                'true' if reuse_settings else 'false'
            )

            logger.info(
                f'SETUP_WIZARD: Reuse scrape settings for batch: '
                f'{reuse_settings}.'
            )

        kodi.set_windowprop(
            'AKL.SetupWizard.PreparedScrapes',
            json.dumps(prepared_scrapes)
        )

        logger.info(
            f'SETUP_WIZARD: Saved prepared game scrape settings '
            f'for collection "{romcollection_id}".'
        )

        logger.info(
            f'SETUP_WIZARD: Prepared game scraper settings: '
            f'{scraper_settings.get_data_dic()}'
        )

        prepare_index_str = kodi.get_windowprop(
            'AKL.SetupWizard.PrepareIndex'
        )

        try:
            prepare_index = int(prepare_index_str)
        except (TypeError, ValueError):
            prepare_index = 0

        prepare_index += 1

        kodi.set_windowprop(
            'AKL.SetupWizard.PrepareIndex',
            str(prepare_index)
        )

        if prepare_index < len(scrape_queue):
            next_collection_id = scrape_queue[prepare_index]

            logger.info(
                f'SETUP_WIZARD: Advancing scrape preparation to '
                f'collection {prepare_index + 1} of '
                f'{len(scrape_queue)}: "{next_collection_id}".'
            )

            AppMediator.async_cmd(
                PREPARE_WIZARD_SYSTEM_SCRAPE,
                {
                    'romcollection_id': next_collection_id
                }
            )
            return

        logger.info(
            f'SETUP_WIZARD: Scrape preparation complete for '
            f'{len(scrape_queue)} queued collection(s).'
        )

        kodi.clear_windowprops([
            'AKL.SetupWizard.PrepareIndex'
        ])

        kodi.dialog_OK(
            kodi.translate(44138),
            kodi.translate(44139)
        )

        logger.info(
            'SETUP_WIZARD: All scrape preparation is complete. '
            'Starting queued scraping.'
        )

        AppMediator.async_cmd(
            'PROCESS_SCRAPE_QUEUE',
            {}
        )

@AppMediator.register(SCRAPE_PREPARED_WIZARD_GAMES)
def cmd_scrape_prepared_wizard_games(args):
    romcollection_id = args.get('romcollection_id')

    if not romcollection_id:
        logger.warning(
            'SETUP_WIZARD: No collection ID supplied for '
            'prepared game scrape.'
        )
        return

    prepared_scrapes_json = kodi.get_windowprop(
        'AKL.SetupWizard.PreparedScrapes'
    )

    try:
        prepared_scrapes = (
            json.loads(prepared_scrapes_json)
            if prepared_scrapes_json
            else {}
        )
    except (TypeError, ValueError):
        logger.warning(
            'SETUP_WIZARD: Invalid prepared scrape data while '
            'starting prepared game scrape.'
        )
        return

    prepared_scrape = prepared_scrapes.get(
        romcollection_id,
        {}
    )

    scraper_id = prepared_scrape.get(
        'game_scraper_id'
    )
    settings_dic = prepared_scrape.get(
        'game_scraper_settings'
    )

    if not scraper_id or not settings_dic:
        logger.warning(
            f'SETUP_WIZARD: Prepared game scrape data is incomplete '
            f'for collection "{romcollection_id}".'
        )
        return

    scraper_settings = ScraperSettings.from_settings_dict(
        settings_dic
    )

    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        addon_repository = AklAddonRepository(uow)
        collection_repository = ROMCollectionRepository(uow)
        source_repository = SourcesRepository(uow)

        collection = collection_repository.find_romcollection(
            romcollection_id
        )

        if collection is None:
            logger.warning(
                f'SETUP_WIZARD: Collection "{romcollection_id}" '
                f'was not found for prepared game scrape.'
            )
            return

        addon = addon_repository.find(
            scraper_id
        )

        if addon is None:
            logger.warning(
                f'SETUP_WIZARD: Prepared game scraper '
                f'"{scraper_id}" was not found.'
            )
            return

        selected_addon = ScraperAddon(
            addon,
            scraper_settings
        )

        sources = source_repository.find_sources_by_collection(
            romcollection_id
        )

        for source in sources:
            _check_unset_asset_dirs(
                source.get_asset_paths(),
                scraper_settings
            )

    logger.info(
        f'SETUP_WIZARD: Starting prepared game scrape for '
        f'"{collection.get_name()}" using scraper '
        f'"{selected_addon.get_name()}".'
    )

    selected_addon.set_scraper_settings(
        scraper_settings
    )

    kodi.notify(
        kodi.translate(40979)
    )

    selected_addon.scrape(
        collection
    )

@AppMediator.register(SCRAPE_ROMS_WITH_SETTINGS)
def cmd_scrape_roms_in_collection_or_source(args):
    romcollection_id: str = args['romcollection_id'] if 'romcollection_id' in args else None
    source_id: str = args['source_id'] if 'source_id' in args else None
    scraper_id: str = args['scraper_id'] if 'scraper_id' in args else None
    scraper_settings: ScraperSettings = args['scraper_settings'] if 'scraper_settings' in args else ScraperSettings.from_addon_settings()

    logger.info(f'cmd_scrape_roms_in_collection_or_source(): SourceID {source_id}, CollectionID {romcollection_id}')
    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        addon_repository = AklAddonRepository(uow)
        collection_repository = ROMCollectionRepository(uow)
        source_repository = SourcesRepository(uow)

        collection = collection_repository.find_romcollection(romcollection_id)
        source = source_repository.find(source_id)
        addon = addon_repository.find(scraper_id)
        selected_addon = ScraperAddon(addon, scraper_settings)

        assets_to_scrape = g_assetFactory.get_asset_list_by_IDs(scraper_settings.asset_IDs_to_scrape)
        metadata_to_scrape = [constants.METADATA_DESCRIPTIONS[meta_id] for meta_id in scraper_settings.metadata_IDs_to_scrape]

        options = collections.OrderedDict()
        options['SCRAPER_METADATA_POLICY'] = kodi.translate(41115).format(kodi.translate(scraper_settings.scrape_metadata_policy))
        options['SCRAPER_ASSET_POLICY'] = kodi.translate(41116).format(kodi.translate(scraper_settings.scrape_assets_policy))
        options['SCRAPER_SEARCH_TERM_MODE'] = kodi.translate(41117).format(kodi.translate(scraper_settings.search_term_mode))
        options['SCRAPER_GAME_SELECTION_MODE'] = kodi.translate(41118).format(kodi.translate(scraper_settings.game_selection_mode))
        options['SCRAPER_ASSET_SELECTION_MODE'] = kodi.translate(41119).format(kodi.translate(scraper_settings.asset_selection_mode))
        options['SCRAPER_META_TO_SCRAPE'] = kodi.translate(42030).format(', '.join(metadata_to_scrape))
        options['SCRAPER_ASSETS_TO_SCRAPE'] = kodi.translate(42031).format(', '.join([a.plural for a in assets_to_scrape]))
        options['SCRAPER_OVERWRITE_META_MODE'] = kodi.translate(42032).format(kodi.translate(42035) if scraper_settings.overwrite_existing_meta else kodi.translate(42036))
        options['SCRAPER_OVERWRITE_ASSETS_MODE'] = kodi.translate(42033).format(kodi.translate(42035) if scraper_settings.overwrite_existing_assets else kodi.translate(42036))
        options['SCRAPER_IGNORE_TITLES_MODE'] = kodi.translate(42034).format(kodi.translate(42035) if scraper_settings.ignore_scrap_title else kodi.translate(42036))
        options['SCRAPE'] = kodi.translate(40881)

        dialog_title = kodi.translate(41000 if source is None else 41111).format(
            collection.get_name() if collection is not None else source.get_name(),
            selected_addon.get_name())
        selected_option = kodi.OrdDictionaryDialog().select(dialog_title, options, preselect='SCRAPE')
        if selected_option is None:
            logger.debug('cmd_scrape_roms_in_collection_or_source() Selected None. Closing context menu')
            del args['scraper_settings']
            ret_cmd = 'SCRAPE_ROMS' if collection is not None else 'SCRAPE_SOURCE_ROMS'
            AppMediator.sync_cmd(ret_cmd, args)
            return

        if selected_option != 'SCRAPE':
            args['ret_cmd'] = SCRAPE_ROMS_WITH_SETTINGS
            AppMediator.sync_cmd(selected_option, args)
            return

        if not source:
            sources = source_repository.find_sources_by_collection(romcollection_id)
            for source in sources:
                _check_unset_asset_dirs(source.get_asset_paths(), scraper_settings)
        else:
            _check_unset_asset_dirs(source.get_asset_paths(), scraper_settings)

    selected_addon.set_scraper_settings(scraper_settings)
    kodi.notify(kodi.translate(40979))
    entity = collection if collection else source

    selected_addon.scrape(entity)


# Scrape ROM - Apply settings and run scrape action
@AppMediator.register('SCRAPE_ROM_WITH_SETTINGS')
def cmd_scrape_rom_with_settings(args):
    rom_id: str = args['rom_id'] if 'rom_id' in args else None
    scraper_id: str = args['scraper_id'] if 'scraper_id' in args else None
    scraper_settings: ScraperSettings = args['scraper_settings'] if 'scraper_settings' in args else ScraperSettings.from_addon_settings()

    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        addon_repository = AklAddonRepository(uow)
        roms_repository = ROMsRepository(uow)

        rom = roms_repository.find_rom(rom_id)
        addon = addon_repository.find(scraper_id)
        selected_addon = ScraperAddon(addon, scraper_settings)

        assets_to_scrape = g_assetFactory.get_asset_list_by_IDs(scraper_settings.asset_IDs_to_scrape)
        metadata_to_scrape = [constants.METADATA_DESCRIPTIONS[meta_id] for meta_id in scraper_settings.metadata_IDs_to_scrape]

        options = collections.OrderedDict()
        options['SCRAPER_METADATA_POLICY'] = kodi.translate(41115).format(kodi.translate(scraper_settings.scrape_metadata_policy))
        options['SCRAPER_ASSET_POLICY'] = kodi.translate(41116).format(kodi.translate(scraper_settings.scrape_assets_policy))
        options['SCRAPER_SEARCH_TERM_MODE'] = kodi.translate(41117).format(kodi.translate(scraper_settings.search_term_mode))
        options['SCRAPER_GAME_SELECTION_MODE'] = kodi.translate(41118).format(kodi.translate(scraper_settings.game_selection_mode))
        options['SCRAPER_ASSET_SELECTION_MODE'] = kodi.translate(41119).format(kodi.translate(scraper_settings.asset_selection_mode))
        options['SCRAPER_META_TO_SCRAPE'] = kodi.translate(42030).format(', '.join(metadata_to_scrape))
        options['SCRAPER_ASSETS_TO_SCRAPE'] = kodi.translate(42031).format(', '.join([a.plural for a in assets_to_scrape]))
        options['SCRAPER_OVERWRITE_META_MODE'] = kodi.translate(42032).format(kodi.translate(42035) if scraper_settings.overwrite_existing_meta else kodi.translate(42036))
        options['SCRAPER_OVERWRITE_ASSETS_MODE'] = kodi.translate(42033).format(kodi.translate(42035) if scraper_settings.overwrite_existing_assets else kodi.translate(42036))
        options['SCRAPER_IGNORE_TITLES_MODE'] = kodi.translate(42034).format(kodi.translate(42035) if scraper_settings.ignore_scrap_title else kodi.translate(42036))
        options['SCRAPE'] = kodi.translate(40881)

        s = kodi.translate(41112).format(rom.get_name(),selected_addon.get_name())
        selected_option = kodi.OrdDictionaryDialog().select(s, options, preselect='SCRAPE')
        if selected_option is None:
            logger.debug('cmd_scrape_rom_with_settings() Selected None. Closing context menu')
            del args['scraper_settings']
            AppMediator.sync_cmd('SCRAPE_ROM', args)
            return

        if selected_option != 'SCRAPE':
            args['ret_cmd'] = 'SCRAPE_ROM_WITH_SETTINGS'
            AppMediator.sync_cmd(selected_option, args)
            return

        # check asset dirs
        source = None
        if rom.get_scanned_by():
            source_repository = SourcesRepository(uow)
            source = source_repository.find(rom.get_scanned_by())

        fallback_asset_paths = g_assetFactory.get_rom_asset_paths(source=source)
        rom.update_missing_asset_paths(fallback_asset_paths)

        _check_unset_asset_dirs(rom.get_asset_paths(), scraper_settings)

        # >> Execute scraper
        selected_addon.set_scraper_settings(scraper_settings)
        kodi.notify(kodi.translate(40979))
        selected_addon.scrape(rom)


@AppMediator.register('SCRAPE_ROM_METADATA')
def cmd_scrape_rom_metadata(args):
    rom_id: str = args['rom_id'] if 'rom_id' in args else None

    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        roms_repository = ROMsRepository(uow)
        rom = roms_repository.find_rom(rom_id)

        scraper_settings = ScraperSettings().from_addon_settings()
        scraper_settings.scrape_metadata_policy = constants.SCRAPE_POLICY_SCRAPE_ONLY
        scraper_settings.scrape_assets_policy = constants.SCRAPE_ACTION_NONE
        scraper_settings.search_term_mode = constants.SCRAPE_MANUAL
        scraper_settings.game_selection_mode = constants.SCRAPE_MANUAL
        scraper_settings.overwrite_existing_meta = True

        selected_addon = _select_scraper(uow, kodi.translate(41122), scraper_settings)
        if selected_addon is None:
            # >> Exits context menu
            logger.debug('SCRAPE_ROM_METADATA: Selected None. Closing context menu')
            AppMediator.sync_cmd('ROM_EDIT_METADATA', args)
            return

        logger.debug(f'SCRAPE_ROM_METADATA: Selected scraper#{selected_addon.get_name()}')
        scraper_settings.metadata_IDs_to_scrape = selected_addon.get_supported_metadata()

        options = collections.OrderedDict()
        for metadata_id in constants.METADATA_IDS:
            if selected_addon.is_metadata_supported(metadata_id):
                options[metadata_id] = constants.METADATA_DESCRIPTIONS[metadata_id]

        selected_options = kodi.MultiSelectDialog().select(kodi.translate(41113), options, preselected=scraper_settings.metadata_IDs_to_scrape)

        if selected_options is not None:
            scraper_settings.metadata_IDs_to_scrape = selected_options

        # check asset dirs
        source = None
        if rom.get_scanned_by():
            source_repository = SourcesRepository(uow)
            source = source_repository.find(rom.get_scanned_by())

        fallback_asset_paths = g_assetFactory.get_rom_asset_paths(source=source)
        rom.update_missing_asset_paths(fallback_asset_paths)

        _check_unset_asset_dirs(rom.get_asset_paths(), scraper_settings)

    # >> Execute scraper
    selected_addon.set_scraper_settings(scraper_settings)
    kodi.notify(kodi.translate(40979))
    selected_addon.scrape(rom)


@AppMediator.register('SCRAPE_ROM_ASSET')
def cmd_scrape_rom_asset(args):
    rom_id: str = args['rom_id'] if 'rom_id' in args else None
    asset_id: str = args['selected_asset'] if 'selected_asset' in args else None

    asset_to_scrape = g_assetFactory.get_asset_info(asset_id)

    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        roms_repository = ROMsRepository(uow)
        rom = roms_repository.find_rom(rom_id)

        scraper_settings = ScraperSettings()
        scraper_settings.scrape_assets_policy = constants.SCRAPE_POLICY_SCRAPE_ONLY
        scraper_settings.scrape_metadata_policy = constants.SCRAPE_ACTION_NONE
        scraper_settings.search_term_mode = constants.SCRAPE_MANUAL
        scraper_settings.game_selection_mode = constants.SCRAPE_MANUAL
        scraper_settings.asset_selection_mode = constants.SCRAPE_MANUAL
        scraper_settings.asset_IDs_to_scrape = [asset_id]
        scraper_settings.overwrite_existing_assets = True

        selected_addon = _select_scraper(uow, kodi.translate(41121).format(asset_to_scrape.name), scraper_settings)
        if selected_addon is None:
            # >> Exits context menu
            logger.debug('SCRAPE_ROM_ASSET: cmd_scrape_rom_asset() Selected None. Closing context menu')
            AppMediator.sync_cmd('ROM_EDIT_ASSETS', args)
            return

        # check asset dirs
        source = None
        if rom.get_scanned_by():
            source_repository = SourcesRepository(uow)
            source = source_repository.find(rom.get_scanned_by())

        fallback_asset_paths = g_assetFactory.get_rom_asset_paths(source=source)
        rom.update_missing_asset_paths(fallback_asset_paths)

        _check_unset_asset_dirs(rom.get_asset_paths(), scraper_settings)

    # >> Execute scraper
    logger.debug(f'SCRAPE_ROM_ASSET: Selected scraper#{selected_addon.get_name()}')

    kodi.notify(kodi.translate(40979))
    selected_addon.scrape(rom)


@AppMediator.register('SCRAPE_ROM_ASSETS')
def cmd_scrape_rom_assets(args):
    rom_id: str = args['rom_id'] if 'rom_id' in args else None

    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        roms_repository = ROMsRepository(uow)
        rom = roms_repository.find_rom(rom_id)

        scraper_settings = ScraperSettings.from_addon_settings()
        scraper_settings.scrape_assets_policy = constants.SCRAPE_POLICY_SCRAPE_ONLY
        scraper_settings.scrape_metadata_policy = constants.SCRAPE_ACTION_NONE
        scraper_settings.search_term_mode = constants.SCRAPE_MANUAL
        scraper_settings.asset_selection_mode = constants.SCRAPE_MANUAL

        selected_addon = _select_scraper(uow, kodi.translate(41120), scraper_settings)
        if selected_addon is None:
            # >> Exits context menu
            logger.debug('SCRAPE_ROM_ASSETS: Selected None. Closing context menu')
            AppMediator.sync_cmd('ROM_EDIT_ASSETS', args)
            return

        logger.debug('SCRAPE_ROM_ASSETS: Selected scraper#{}'.format(selected_addon.get_name()))
        scraper_settings.asset_IDs_to_scrape = selected_addon.get_supported_assets()

        asset_options = g_assetFactory.get_all()
        options = collections.OrderedDict()
        for asset_option in asset_options:
            if selected_addon.is_asset_supported(asset_option.id):
                options[asset_option.id] = kodi.translate(asset_option.name_id)

        selected_options = kodi.MultiSelectDialog().select(
            kodi.translate(41114), options, preselected=scraper_settings.asset_IDs_to_scrape)

        if selected_options is not None:
            scraper_settings.asset_IDs_to_scrape = selected_options

        scraper_settings.overwrite_existing_assets = kodi.dialog_yesno(kodi.translate(41061))

        # check asset dirs
        source = None
        if rom.get_scanned_by():
            source_repository = SourcesRepository(uow)
            source = source_repository.find(rom.get_scanned_by())

        fallback_asset_paths = g_assetFactory.get_rom_asset_paths(source=source)
        rom.update_missing_asset_paths(fallback_asset_paths)

        _check_unset_asset_dirs(rom.get_asset_paths(), scraper_settings)

    selected_addon.set_scraper_settings(scraper_settings)
    kodi.notify(kodi.translate(40979))
    # >> Execute scraper
    selected_addon.scrape(rom)


# -------------------------------------------------------------------------------------------------
# Scraper settings configuration
# -------------------------------------------------------------------------------------------------
@AppMediator.register('SCRAPER_METADATA_POLICY')
def cmd_configure_scraper_metadata_policy(args):
    scraper_settings: ScraperSettings = args['scraper_settings'] if 'scraper_settings' in args else ScraperSettings.from_addon_settings()

    options = collections.OrderedDict()
    options[constants.SCRAPE_ACTION_NONE] = kodi.translate(constants.SCRAPE_ACTION_NONE)
    options[constants.SCRAPE_POLICY_TITLE_ONLY] = kodi.translate(constants.SCRAPE_POLICY_TITLE_ONLY)
    options[constants.SCRAPE_POLICY_LOCAL_AND_SCRAPE] = kodi.translate(constants.SCRAPE_POLICY_LOCAL_AND_SCRAPE)
    options[constants.SCRAPE_POLICY_SCRAPE_ONLY] = kodi.translate(constants.SCRAPE_POLICY_SCRAPE_ONLY)

    s = kodi.translate(41115).format(kodi.translate(scraper_settings.scrape_metadata_policy))
    selected_option = kodi.OrdDictionaryDialog().select(s, options, preselect=scraper_settings.scrape_metadata_policy)

    if selected_option is None:
        AppMediator.sync_cmd(args['ret_cmd'], args)
        return

    scraper_settings.scrape_metadata_policy = selected_option
    args['scraper_settings'] = scraper_settings
    AppMediator.sync_cmd(args['ret_cmd'], args)
    return


@AppMediator.register('SCRAPER_ASSET_POLICY')
def cmd_configure_scraper_asset_policy(args):
    scraper_settings: ScraperSettings = args['scraper_settings'] if 'scraper_settings' in args else ScraperSettings.from_addon_settings()

    options = collections.OrderedDict()
    options[constants.SCRAPE_ACTION_NONE] = kodi.translate(constants.SCRAPE_ACTION_NONE)
    options[constants.SCRAPE_POLICY_LOCAL_ONLY] = kodi.translate(constants.SCRAPE_POLICY_LOCAL_ONLY)
    options[constants.SCRAPE_POLICY_LOCAL_AND_SCRAPE] = kodi.translate(constants.SCRAPE_POLICY_LOCAL_AND_SCRAPE)
    options[constants.SCRAPE_POLICY_SCRAPE_ONLY] = kodi.translate(constants.SCRAPE_POLICY_SCRAPE_ONLY)

    s = kodi.translate(41116).format(kodi.translate(scraper_settings.scrape_assets_policy))
    selected_option = kodi.OrdDictionaryDialog().select(s, options, preselect=scraper_settings.scrape_assets_policy)

    if selected_option is None:
        AppMediator.sync_cmd(args['ret_cmd'], args)
        return

    scraper_settings.scrape_assets_policy = selected_option
    args['scraper_settings'] = scraper_settings
    AppMediator.sync_cmd(args['ret_cmd'], args)


@AppMediator.register('SCRAPER_SEARCH_TERM_MODE')
def cmd_configure_scraper_search_term_mode(args):
    scraper_settings: ScraperSettings = args['scraper_settings'] if 'scraper_settings' in args else ScraperSettings.from_addon_settings()

    options = collections.OrderedDict()
    options[constants.SCRAPE_MANUAL] = kodi.translate(constants.SCRAPE_MANUAL)
    options[constants.SCRAPE_AUTOMATIC] = kodi.translate(constants.SCRAPE_AUTOMATIC)
    s = kodi.translate(41117).format(kodi.translate(scraper_settings.search_term_mode))
    selected_option = kodi.OrdDictionaryDialog().select(s, options, preselect=scraper_settings.search_term_mode)

    if selected_option is None:
        AppMediator.sync_cmd(args['ret_cmd'], args)
        return

    scraper_settings.search_term_mode = selected_option
    args['scraper_settings'] = scraper_settings
    AppMediator.sync_cmd(args['ret_cmd'], args)
    return


@AppMediator.register('SCRAPER_GAME_SELECTION_MODE')
def cmd_configure_scraper_game_selection_mode(args):
    scraper_settings: ScraperSettings = args['scraper_settings'] if 'scraper_settings' in args else ScraperSettings.from_addon_settings()

    options = collections.OrderedDict()
    options[constants.SCRAPE_MANUAL] = kodi.translate(constants.SCRAPE_MANUAL)
    options[constants.SCRAPE_AUTOMATIC] = kodi.translate(constants.SCRAPE_AUTOMATIC)
    s = kodi.translate(41118).format(kodi.translate(scraper_settings.game_selection_mode))
    selected_option = kodi.OrdDictionaryDialog().select(s, options, preselect=scraper_settings.game_selection_mode)

    if selected_option is None:
        AppMediator.sync_cmd(args['ret_cmd'], args)
        return

    scraper_settings.game_selection_mode = selected_option
    args['scraper_settings'] = scraper_settings
    AppMediator.sync_cmd(args['ret_cmd'], args)
    return


@AppMediator.register('SCRAPER_ASSET_SELECTION_MODE')
def cmd_configure_scraper_asset_selection_mode(args):
    scraper_settings: ScraperSettings = args['scraper_settings'] if 'scraper_settings' in args else ScraperSettings.from_addon_settings()

    options = collections.OrderedDict()
    options[constants.SCRAPE_MANUAL] = kodi.translate(constants.SCRAPE_MANUAL)
    options[constants.SCRAPE_AUTOMATIC] = kodi.translate(constants.SCRAPE_AUTOMATIC)
    s = kodi.translate(41119).format(kodi.translate(scraper_settings.asset_selection_mode))
    selected_option = kodi.OrdDictionaryDialog().select(s, options, preselect=scraper_settings.asset_selection_mode)

    if selected_option is None:
        AppMediator.sync_cmd(args['ret_cmd'], args)
        return

    scraper_settings.asset_selection_mode = selected_option
    args['scraper_settings'] = scraper_settings
    AppMediator.sync_cmd(args['ret_cmd'], args)
    return


@AppMediator.register('SCRAPER_META_TO_SCRAPE')
def cmd_configure_scraper_metadata_to_scrape(args):
    scraper_settings: ScraperSettings = args['scraper_settings'] if 'scraper_settings' in args else ScraperSettings.from_addon_settings()
    scraper_supported_metadata: list = args['scraper_supported_metadata'] if 'scraper_supported_metadata' in args else []

    options = collections.OrderedDict()
    for metadata_id in constants.METADATA_IDS:
        if scraper_supported_metadata is None or metadata_id in scraper_supported_metadata:
            options[metadata_id] = constants.METADATA_DESCRIPTIONS[metadata_id]

    selected_options = kodi.MultiSelectDialog().select(kodi.translate(41113), options, preselected=scraper_settings.metadata_IDs_to_scrape)

    if selected_options is None:
        AppMediator.sync_cmd(args['ret_cmd'], args)
        return

    scraper_settings.metadata_IDs_to_scrape = selected_options
    args['scraper_settings'] = scraper_settings
    AppMediator.sync_cmd(args['ret_cmd'], args)
    return


@AppMediator.register('SCRAPER_ASSETS_TO_SCRAPE')
def cmd_configure_scraper_assets_to_scrape(args):
    scraper_settings: ScraperSettings = args['scraper_settings'] if 'scraper_settings' in args else ScraperSettings.from_addon_settings()
    supported_assets: list = args['scraper_supported_assets'] if 'scraper_supported_assets' in args else []

    asset_options = g_assetFactory.get_all()
    options = collections.OrderedDict()
    for asset_option in asset_options:
        if supported_assets is None or asset_option.id in supported_assets:
            options[asset_option.id] = kodi.translate(asset_option.name_id)

    selected_options = kodi.MultiSelectDialog().select(kodi.translate(41114), options, preselected=scraper_settings.asset_IDs_to_scrape)

    if selected_options is None:
        AppMediator.sync_cmd(args['ret_cmd'], args)
        return

    scraper_settings.asset_IDs_to_scrape = selected_options
    args['scraper_settings'] = scraper_settings
    AppMediator.sync_cmd(args['ret_cmd'], args)
    return


@AppMediator.register('SCRAPER_OVERWRITE_META_MODE')
def cmd_configure_scraper_overwrite_meta_mode(args):
    scraper_settings: ScraperSettings = args['scraper_settings'] if 'scraper_settings' in args else ScraperSettings.from_addon_settings()
    scraper_settings.overwrite_existing_meta = not scraper_settings.overwrite_existing_meta
    args['scraper_settings'] = scraper_settings
    AppMediator.sync_cmd(args['ret_cmd'], args)


@AppMediator.register('SCRAPER_OVERWRITE_ASSETS_MODE')
def cmd_configure_scraper_overwrite_assets_mode(args):
    scraper_settings: ScraperSettings = args['scraper_settings'] if 'scraper_settings' in args else ScraperSettings.from_addon_settings()
    scraper_settings.overwrite_existing_assets = not scraper_settings.overwrite_existing_assets
    args['scraper_settings'] = scraper_settings
    AppMediator.sync_cmd(args['ret_cmd'], args)


@AppMediator.register('SCRAPER_IGNORE_TITLES_MODE')
def cmd_configure_scraper_ignore_mode(args):
    scraper_settings: ScraperSettings = args['scraper_settings'] if 'scraper_settings' in args else ScraperSettings.from_addon_settings()
    scraper_settings.ignore_scrap_title = not scraper_settings.ignore_scrap_title
    args['scraper_settings'] = scraper_settings
    AppMediator.sync_cmd(args['ret_cmd'], args)


def _select_scraper(uow: UnitOfWork, title: str, scraper_settings: ScraperSettings) -> ScraperAddon:
    selected_addon = None
    repository = AklAddonRepository(uow)
    addons = repository.find_all_scraper_addons()

    # --- Make a menu list of available metadata scrapers ---
    options = {}
    for addon in addons:
        scraper_addon = ScraperAddon(addon, scraper_settings)
        if scraper_addon.settings_are_applicable():
            options[scraper_addon] = addon.get_name()

    selected_addon: ScraperAddon = kodi.OrdDictionaryDialog().select(title, options)
    return selected_addon


def _check_unset_asset_dirs(asset_paths: typing.List[AssetPath], scraper_settings: ScraperSettings) -> bool:
    logger.debug('_check_launcher_unset_asset_sdirs() ...')

    unconfigured_name_list = []
    not_existing_list: typing.List[AssetPath] = []
    enabled_asset_list = []
    for asset_id in scraper_settings.asset_IDs_to_scrape:
        rom_asset = g_assetFactory.get_asset_info(asset_id)
        asset_path = next((ap for ap in asset_paths if ap.asset_info.id == rom_asset.id), None)

        if asset_path is None:
            logger.debug(f'Directory not set. Asset "{rom_asset}" will be disabled')
            unconfigured_name_list.append(rom_asset.name)
        elif not asset_path.get_path_FN().exists():
            logger.debug(f'Directory not existing. If not created asset "{rom_asset}" will be disabled')
            not_existing_list.append(asset_path)
        else:
            enabled_asset_list.append(rom_asset.id)

    if not_existing_list:
        not_existing_names = ', '.join([n.get_asset_info().name for n in not_existing_list])
        msg = kodi.translate(41198).format(not_existing_names)
        logger.debug(msg)
        if kodi.dialog_yesno(msg):
            for ap in not_existing_list:
                ap.get_path_FN().makedirs()
                enabled_asset_list.append(ap.get_asset_info().id)
        else:
            unconfigured_name_list.extend([ap.get_asset_info().name for ap in not_existing_list])

    scraper_settings.asset_IDs_to_scrape = enabled_asset_list
    if unconfigured_name_list:
        unconfigured_asset_srt = ', '.join(unconfigured_name_list)
        msg = kodi.translate(41149).format(unconfigured_asset_srt)
        logger.debug(msg)
        kodi.dialog_OK(msg)
        return False
    return True
