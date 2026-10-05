# -*- coding: utf-8 -*-
#
# Advanced Kodi Launcher: Commands (API actions)
##
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# Commands executed by the webservice API
#

# --- Python standard library ---
from __future__ import unicode_literals
from __future__ import division

import logging
import json
from akl.scrapers import ScraperSettings

from akl.utils import kodi, io
from akl.api import ROMObj, MetaDataObj
from akl import constants, platforms

from resources.lib.commands.mediator import AppMediator
from resources.lib import globals
from resources.lib.repositories import (
    UnitOfWork,
    CategoryRepository,
    ROMCollectionRepository,
    ROMsRepository,
    SourcesRepository
)
from resources.lib.repositories import AklAddonRepository, LaunchersRepository
from resources.lib.domain import (
    ROM,
    ROMCollection,
    ROMLauncherAddon,
    RuleSet,
    g_assetFactory
)

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------------------------------
# ROMCollection API commands
# -------------------------------------------------------------------------------------------------
def cmd_set_launcher_args(args) -> bool:
    launcher_id: str = args['launcher_id'] if 'launcher_id' in args else None
    addon_id: str = args['addon_id'] if 'addon_id' in args else None
    launcher_settings = args['settings'] if 'settings' in args else None

    entity_type = args['entity_type'] if 'entity_type' in args else None
    entity_id: str = args['entity_id'] if 'entity_id' in args else None

    redirect_to_action = None
    args = None
    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        addon_repository = AklAddonRepository(uow)
        launchers_repository = LaunchersRepository(uow)

        addon = addon_repository.find_by_addon_id(addon_id, constants.AddonType.LAUNCHER)
        launcher = launchers_repository.find(launcher_id)

        if launcher is None:
            launcher = ROMLauncherAddon(None, addon)
            launcher.set_settings(launcher_settings)
            launchers_repository.insert_launcher(launcher)
        else:
            launcher.set_settings(launcher_settings)
            launchers_repository.update_launcher(launcher)

        if entity_type:
            if entity_type == constants.OBJ_ROM:
                entity_repo = ROMsRepository(uow)
                rom = entity_repo.find_rom(entity_id)
                rom.add_launcher(launcher)
                entity_repo.update_rom(rom)
                redirect_to_action = "EDIT_ROM_LAUNCHERS"
                args = {'rom_id': entity_id}

            if entity_type == constants.OBJ_ROMCOLLECTION:
                entity_repo = ROMCollectionRepository(uow)
                collection = entity_repo.find_romcollection(entity_id)
                collection.add_launcher(launcher)
                entity_repo.update_romcollection(collection)
                redirect_to_action = "EDIT_ROMCOLLECTION_LAUNCHERS"
                args = {'romcollection_id': entity_id}

            if entity_type == constants.OBJ_SOURCE:
                entity_repo = SourcesRepository(uow)
                source = entity_repo.find(entity_id)
                source.add_launcher(launcher)
                entity_repo.update_source(source)
                redirect_to_action = "EDIT_SOURCE_LAUNCHERS"
                args = {'source_id': entity_id}

        uow.commit()

    kodi.refresh_container()
    kodi.notify(kodi.translate(41005).format(launcher.get_name()))

    setup_wizard_source_id = kodi.get_windowprop(
        'AKL.SetupWizard.SourceID'
    )

    if (
        entity_type == constants.OBJ_SOURCE
        and entity_id
        and setup_wizard_source_id == entity_id
    ):

        kodi.clear_windowprops([
            'AKL.SetupWizard.SourceID'
        ])

        logger.info(
            f'SETUP_WIZARD: Cleared launcher continuation marker for '
            f'source "{entity_id}".'
        )

        kodi.set_windowprop(
            'AKL.SetupWizard.ScannerSourceID',
            entity_id
        )

        logger.info(
            f'SETUP_WIZARD: Set scanner continuation marker for '
            f'source "{entity_id}".'
        )

        logger.info(
            f'SETUP_WIZARD: Continuing to scanner configuration for '
            f'source "{entity_id}".'
        )

        AppMediator.async_cmd(
            'SOURCE_EDIT_SCANNER',
            {'source_id': entity_id}
        )

    elif entity_type:
        AppMediator.async_cmd(redirect_to_action, args)

    return True


# -------------------------------------------------------------------------------------------------
# Source scanner API commands
# -------------------------------------------------------------------------------------------------
def cmd_set_scanner_settings(args) -> bool:
    # TODO: backwards compatiblity
    romcollection_id: str = args['romcollection_id'] if 'romcollection_id' in args else None
    source_id: str = args['source_id'] if 'source_id' in args else None
    source_id = romcollection_id if not source_id else source_id

    settings: dict = args['settings'] if 'settings' in args else None

    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        src_repository = SourcesRepository(uow)
        source = src_repository.find(source_id)

        source.set_settings(settings)

        src_repository.update_source(source)
        uow.commit()

    kodi.notify(kodi.translate(41006).format(source.addon.get_name()))
    AppMediator.async_cmd('RENDER_SOURCES_VIEW')

    if kodi.dialog_yesno(kodi.translate(41051)):
        setup_wizard_source_id = kodi.get_windowprop(
            'AKL.SetupWizard.ScannerSourceID'
        )

        if setup_wizard_source_id == source_id:
            logger.info(
                f'SETUP_WIZARD: Scanner configuration completed for '
                f'source "{source_id}". Starting ROM scan.'
            )

        AppMediator.async_cmd(
            'SCAN_ROMS',
            {'source_id': source_id}
        )
    else:
        setup_wizard_source_id = kodi.get_windowprop(
            'AKL.SetupWizard.ScannerSourceID'
        )

        if setup_wizard_source_id == source_id:
            logger.info(
                f'SETUP_WIZARD: ROM scan declined for source '
                f'"{source_id}". Continuing setup without scanning.'
            )

            cmd_store_scanned_roms({
                'source_id': source_id,
                'roms': []
            })
        else:
            AppMediator.async_cmd(
                'SOURCE_MANAGE_ROMS',
                {'source_id': source_id}
            )

    return True


def cmd_store_scanned_roms(args) -> bool:
    # TODO: backwards compatiblity
    romcollection_id: str = args['romcollection_id'] if 'romcollection_id' in args else None
    source_id: str = args['source_id'] if 'source_id' in args else None
    source_id = romcollection_id if not source_id else source_id

    new_roms: list = args['roms'] if 'roms' in args else None

    if new_roms is None:
        update_collection_id = kodi.get_windowprop(
            'AKL.UpdateCollection.CollectionID'
        )

        if update_collection_id:
            logger.warning(
                'UPDATE_ROMCOLLECTION: Scan did not return ROM data. '
                'Cancelling collection update.'
            )
            kodi.clear_windowprops(
                [
                    'CollectionID',
                    'SourceQueue'
                ],
                prefix='AKL.UpdateCollection.'
            )
            kodi.notify_warn('ROM collection update was not completed.')
            return False

        AppMediator.async_cmd(
            'SOURCE_MANAGE_ROMS',
            {'source_id': source_id}
        )
        return

    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        rom_repository = ROMsRepository(uow)
        src_repository = SourcesRepository(uow)
        source = src_repository.find(source_id)

        for rom_data in new_roms:
            api_rom_obj = ROMObj(rom_data)

            rom_obj = ROM()
            rom_obj.update_with(api_rom_obj, overwrite_existing_metadata=True, update_scanned_data=True)
            rom_obj.set_platform(source.get_platform())
            rom_obj.scanned_by(source.get_id())
            rom_obj.apply_source_asset_paths(source)

            rom_repository.insert_rom(rom_obj)
        uow.commit()

    kodi.notify(kodi.translate(41007).format(source.get_name()))

    AppMediator.async_cmd('RENDER_SOURCE_VIEW', {'source_id': source_id})
    AppMediator.async_cmd(
        'RENDER_VCATEGORY_VIEW',
        {'vcategory_id': constants.VCATEGORY_TITLE_ID}
    )

    # --- Update ROM Collection continuation ---
    update_collection_id = kodi.get_windowprop(
        'AKL.UpdateCollection.CollectionID'
    )
    update_source_queue_json = kodi.get_windowprop(
        'AKL.UpdateCollection.SourceQueue'
    )

    if update_collection_id and update_source_queue_json:
        try:
            update_source_queue = json.loads(update_source_queue_json)
        except (TypeError, ValueError):
            logger.exception(
                'UPDATE_ROMCOLLECTION: Could not decode source queue.'
            )
            kodi.clear_windowprops(
                [
                    'CollectionID',
                    'SourceQueue'
                ],
                prefix='AKL.UpdateCollection.'
            )
            return False

        # Only consume the callback if it belongs to the source currently
        # expected by the Update ROM Collection workflow.
        if update_source_queue and update_source_queue[0] == source_id:
            completed_source_id = update_source_queue.pop(0)

            logger.info(
                'UPDATE_ROMCOLLECTION: Completed source "{}". {} source(s) remaining.'.format(
                    completed_source_id,
                    len(update_source_queue)
                )
            )

            if update_source_queue:
                # Save the shortened queue before launching the next scanner.
                kodi.set_windowprop(
                    'AKL.UpdateCollection.SourceQueue',
                    json.dumps(update_source_queue)
                )

                next_source_id = update_source_queue[0]

                logger.info(
                    'UPDATE_ROMCOLLECTION: Scanning next source "{}".'.format(
                        next_source_id
                    )
                )

                AppMediator.async_cmd(
                    'SCAN_ROMS',
                    {
                        'source_id': next_source_id,
                        'force': True
                    }
                )
                return True

            # All required sources have completed. Clear continuation state
            # before importing so a later scan cannot accidentally resume it.
            kodi.clear_windowprops(
                [
                    'CollectionID',
                    'SourceQueue'
                ],
                prefix='AKL.UpdateCollection.'
            )

            logger.info(
                'UPDATE_ROMCOLLECTION: All source scans completed. '
                'Executing import rulesets for collection "{}".'.format(
                    update_collection_id
                )
            )

            AppMediator.async_cmd(
                'EXECUTE_ALL_RULESETS',
                {
                    'romcollection_id': update_collection_id
                }
            )
            return True

    setup_wizard_source_id = kodi.get_windowprop(
        'AKL.SetupWizard.ScannerSourceID'
    )

    if setup_wizard_source_id != source_id:
        AppMediator.async_cmd(
            'SOURCE_MANAGE_ROMS',
            {'source_id': source_id}
        )
        return True

    category_id = kodi.get_windowprop(
        'AKL.SetupWizard.CategoryID'
    )

    logger.info(
        f'SETUP_WIZARD: ROM scan completed for source '
        f'"{source.get_name()}" ({source_id}).'
    )

    logger.info(
        f'SETUP_WIZARD: Creating game collection in category '
        f'"{category_id}".'
    )

    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        category_repository = CategoryRepository(uow)
        romcollection_repository = ROMCollectionRepository(uow)

        parent_category = category_repository.find_category(
            category_id
        )

        romcollection = ROMCollection()
        romcollection.set_name(source.get_name())
        romcollection.set_platform(source.get_platform())

        platform = platforms.get_AKL_platform(
            source.get_platform()
        )
        romcollection.set_box_sizing(
            platform.default_box_size
        )

        romcollection_repository.insert_romcollection(
            romcollection,
            parent_category
        )

        ruleset = RuleSet()
        ruleset.apply_source(source)

        romcollection_repository.add_ruleset_to_romcollection(
            romcollection.get_id(),
            ruleset
        )

        uow.commit()

    AppMediator.async_cmd(
        'RENDER_ROMCOLLECTION_VIEW',
        {'romcollection_id': romcollection.get_id()}
    )

    AppMediator.async_cmd(
        'RENDER_CATEGORY_VIEW',
        {'category_id': category_id}
    )

    logger.info(
        f'SETUP_WIZARD: Created game collection '
        f'"{romcollection.get_name()}" '
        f'({romcollection.get_id()}) from source "{source_id}".'
    )

    logger.info(
        f'SETUP_WIZARD: Created import ruleset for source '
        f'"{source_id}".'
    )

    kodi.clear_windowprops([
        'AKL.SetupWizard.ScannerSourceID',
        'AKL.SetupWizard.CategoryID'
    ])

    logger.info(
        'SETUP_WIZARD: Cleared scanner and category '
        'continuation markers.'
    )

    kodi.set_windowprop(
        'AKL.SetupWizard.CollectionID',
        romcollection.get_id()
    )

    logger.info(
        f'SETUP_WIZARD: Set collection continuation marker for '
        f'"{romcollection.get_id()}".'
    )

    AppMediator.async_cmd(
        'EXECUTE_ALL_RULESETS',
        {'romcollection_id': romcollection.get_id()}
    )

    return True


def cmd_remove_roms(args) -> bool:
    # TODO: backwards compatiblity
    romcollection_id: str = args['romcollection_id'] if 'romcollection_id' in args else None
    source_id: str = args['source_id'] if 'source_id' in args else None
    source_id = romcollection_id if not source_id else source_id

    rom_ids: list = args['rom_ids'] if 'rom_ids' in args else None
    if rom_ids is None:
        return

    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        sources_repository = SourcesRepository(uow)
        romcollections_repository = ROMCollectionRepository(uow)
        rom_repository = ROMsRepository(uow)

        romcollections = [*romcollections_repository.find_romcollections_by_source(source_id)]
        source = sources_repository.find(source_id)

        for rom_id in rom_ids:
            rom_repository.delete_rom(rom_id)
        uow.commit()

    kodi.notify(kodi.translate(41010).format(source.get_name()))

    if source_id:
        AppMediator.async_cmd('RENDER_SOURCE_VIEW', {'source_id': source_id})
    for collection in romcollections:
        AppMediator.async_cmd('RENDER_ROMCOLLECTION_VIEW', {'romcollection_id': collection.get_id()})
    AppMediator.async_cmd('RENDER_VCATEGORY_VIEWS')
    for romcollection in romcollections:
        AppMediator.async_cmd('RENDER_ROMCOLLECTION_VIEW', {'romcollection_id': romcollection.get_id()})
    AppMediator.async_cmd('EDIT_SOURCE', {'source_id': source_id})
    return True


def cmd_store_scraped_roms(args) -> bool:
    entity_type = args['entity_type'] if 'entity_type' in args else None
    entity_id: str = args['entity_id'] if 'entity_id' in args else None
    scraped_roms: list = args['roms'] if 'roms' in args else None
    settings_dic: dict = args['applied_settings'] if 'applied_settings' in args else {}
    applied_settings = ScraperSettings.from_settings_dict(settings_dic)

    if scraped_roms is None:
        return

    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        source_repository = SourcesRepository(uow)
        romcollection_repository = ROMCollectionRepository(uow)
        rom_repository = ROMsRepository(uow)

        entity_name = 'UNKNOWN'
        if entity_type == constants.OBJ_SOURCE:
            source = source_repository.find(entity_id)
            existing_roms = rom_repository.find_roms_by_source(source)
            entity_name = source.get_name()

        if entity_type == constants.OBJ_ROMCOLLECTION:
            romcollection = romcollection_repository.find_romcollection(entity_id)
            existing_roms = rom_repository.find_roms_by_romcollection(romcollection)
            entity_name = romcollection.get_name()

        existing_roms_by_id = {rom.get_id(): rom for rom in existing_roms}

        metadata_is_updated = applied_settings.scrape_metadata_policy != constants.SCRAPE_ACTION_NONE
        assets_are_updated = applied_settings.scrape_assets_policy != constants.SCRAPE_ACTION_NONE

        metadata_to_update = applied_settings.metadata_IDs_to_scrape if metadata_is_updated else []
        assets_to_update = applied_settings.asset_IDs_to_scrape if assets_are_updated else []

        logger.debug('========================== Applied scraper settings ==========================')
        logger.debug('Metadata IDs:         {}'.format(', '.join(applied_settings.metadata_IDs_to_scrape)))
        logger.debug('Asset IDs:            {}'.format(', '.join(applied_settings.asset_IDs_to_scrape)))
        logger.debug('Overwrite existing:')
        logger.debug(' - Metadata           {}'.format('Yes' if applied_settings.overwrite_existing_meta else 'No'))
        logger.debug(' - Assets             {}'.format('Yes' if applied_settings.overwrite_existing_assets else 'No'))

        for rom_data in scraped_roms:
            api_rom_obj = ROMObj(rom_data)

            if api_rom_obj.get_id() not in existing_roms_by_id:
                logger.warning('Scraped ROM {} with ID {} could not be found in {}#{} {}. Will be skipped.'.format(
                    api_rom_obj.get_name(),
                    api_rom_obj.get_id(),
                    kodi.translate(entity_type),
                    entity_id,
                    entity_name))
                continue

            rom_obj = existing_roms_by_id[api_rom_obj.get_id()]
            rom_obj.update_with(
                api_rom_obj,
                metadata_to_update,
                assets_to_update,
                overwrite_existing_metadata=applied_settings.overwrite_existing_meta,
                overwrite_existing_assets=applied_settings.overwrite_existing_assets,
                update_scanned_data=not applied_settings.ignore_scrap_title)
            # rom_obj.scraped_with(scraper_id)

            rom_repository.update_rom(rom_obj)
        uow.commit()

    kodi.notify(kodi.translate(41008).format(entity_name))

    if metadata_is_updated:
        AppMediator.async_cmd('RENDER_VCATEGORY_VIEWS')

    if entity_type == constants.OBJ_ROMCOLLECTION:
        AppMediator.async_cmd(
            'RENDER_ROMCOLLECTION_VIEW',
            {'romcollection_id': entity_id}
        )

        setup_wizard_collection_id = kodi.get_windowprop(
            'AKL.SetupWizard.GameScrapeCollectionID'
        )

        if setup_wizard_collection_id == entity_id:
            kodi.clear_windowprops([
                'AKL.SetupWizard.GameScrapeCollectionID'
            ])

            logger.info(
                f'SETUP_WIZARD: Game scrape completed for collection '
                f'"{entity_id}".'
            )

            logger.info(
                f'SETUP_WIZARD: Cleared game scrape continuation marker '
                f'for collection "{entity_id}".'
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
                    'SETUP_WIZARD: Invalid scrape queue found '
                    'after game scrape.'
                )
                scrape_queue = []

            if entity_id in scrape_queue:
                scrape_queue.remove(entity_id)

            kodi.set_windowprop(
                'AKL.SetupWizard.ScrapeQueue',
                json.dumps(scrape_queue)
            )

            logger.info(
                f'SETUP_WIZARD: Removed completed collection '
                f'"{entity_id}" from scrape queue. '
                f'{len(scrape_queue)} collection(s) remain.'
            )

            if scrape_queue:
                logger.info(
                    'SETUP_WIZARD: Continuing to next queued collection.'
                )

                AppMediator.async_cmd(
                    'PROCESS_SCRAPE_QUEUE',
                    {}
                )
            else:
                kodi.clear_windowprops([
                    'AKL.SetupWizard.ScrapeQueue',
                    'AKL.SetupWizard.PreparedScrapes',
                    'AKL.SetupWizard.PrepareIndex',
                    'AKL.SetupWizard.SystemScrapeSettings',
                    'AKL.SetupWizard.GameScrapeSettings',
                    'AKL.SetupWizard.ReuseScrapeSettings',
                    'AKL.SetupWizard.SystemScrapeCollectionID',
                    'AKL.SetupWizard.GameScrapeCollectionID'
                ])

                logger.info(
                    'SETUP_WIZARD: All queued scraping is complete.'
                )

                kodi.dialog_OK(
                    kodi.translate(44126),
                    kodi.translate(44117)
                )

                AppMediator.sync_cmd(
                    'SHOW_AKL_SETUP_COMPLETE',
                    {}
                )

    if entity_type == constants.OBJ_SOURCE:
        AppMediator.async_cmd(
            'RENDER_SOURCE_VIEW',
            {'source_id': entity_id}
        )

        kodi.dialog_OK(
            kodi.translate(44127).format(
                entity_name
            ),
            kodi.translate(44128)
        )

    return True


def cmd_store_scraped_system(args) -> bool:
    romcollection_id: str = (
        args['romcollection_id']
        if 'romcollection_id' in args
        else None
    )
    system_data: dict = (
        args['system']
        if 'system' in args
        else None
    )

    if not romcollection_id or system_data is None:
        logger.error(
            'SYSTEM_SCRAPE: Missing ROM collection ID or system data.'
        )
        return False

    logger.info(
        f'SYSTEM_SCRAPE: Storing scraped system data for '
        f'collection "{romcollection_id}".'
    )

    system_obj = MetaDataObj(system_data)

    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        romcollection_repository = ROMCollectionRepository(uow)
        romcollection = romcollection_repository.find_romcollection(
            romcollection_id
        )

        if romcollection is None:
            logger.error(
                f'SYSTEM_SCRAPE: ROM collection '
                f'"{romcollection_id}" was not found.'
            )
            return False

        # Do not replace the user-selected collection/display name.

        if system_obj.get_releaseyear():
            romcollection.set_releaseyear(
                system_obj.get_releaseyear()
            )

        if system_obj.get_developer():
            romcollection.set_developer(
                system_obj.get_developer()
            )

        if system_obj.get_plot():
            romcollection.set_plot(
                system_obj.get_plot()
            )

        for asset_id in romcollection.get_asset_ids_list():
            new_asset = system_obj.get_asset(asset_id)

            if new_asset is None:
                continue

            if asset_id == constants.ASSET_TRAILER_ID:
                romcollection.set_trailer(new_asset)
            else:
                asset_info = g_assetFactory.get_asset_info(
                    asset_id
                )
                asset_path = io.FileName(new_asset)
                romcollection.set_asset(
                    asset_info,
                    asset_path
                )

        romcollection_repository.update_romcollection(
            romcollection
        )

        uow.commit()

    AppMediator.async_cmd(
        'RENDER_ROMCOLLECTION_VIEW',
        {'romcollection_id': romcollection_id}
    )

    AppMediator.async_cmd(
        'RENDER_CATEGORY_VIEW',
        {'category_id': romcollection.get_parent_id()}
    )

    logger.info(
        f'SYSTEM_SCRAPE: Stored scraped system data for '
        f'collection "{romcollection_id}".'
    )

    setup_wizard_collection_id = kodi.get_windowprop(
        'AKL.SetupWizard.SystemScrapeCollectionID'
    )

    if setup_wizard_collection_id == romcollection_id:
        kodi.clear_windowprops([
            'AKL.SetupWizard.SystemScrapeCollectionID'
        ])

        logger.info(
            f'SETUP_WIZARD: Cleared system scrape continuation marker '
            f'for collection "{romcollection_id}".'
        )

        kodi.set_windowprop(
            'AKL.SetupWizard.GameScrapeCollectionID',
            romcollection_id
        )

        logger.info(
            f'SETUP_WIZARD: Set game scrape continuation marker '
            f'for collection "{romcollection_id}".'
        )

        logger.info(
            f'SETUP_WIZARD: System scrape completed. Continuing to '
            f'game scrape for collection "{romcollection_id}".'
        )

        AppMediator.async_cmd(
            'SCRAPE_PREPARED_WIZARD_GAMES',
            {'romcollection_id': romcollection_id}
        )
        
    bulk_collection_id = kodi.get_windowprop(
        'AKL.BulkSystemScrape.CurrentCollectionID'
    )

    if bulk_collection_id == romcollection_id:
        logger.info(
            f'BULK_SYSTEM_SCRAPE: System scrape completed for collection '
            f'"{romcollection_id}".'
        )

        kodi.clear_windowprops([
            'AKL.BulkSystemScrape.CurrentCollectionID'
        ])

        AppMediator.async_cmd(
            'PROCESS_BULK_SYSTEM_SCRAPE_QUEUE',
            {}
        )

    return True


def cmd_store_scraped_single_rom(args) -> bool:
    rom_id: str = args['rom_id'] if 'rom_id' in args else None
    scraped_rom_data: dict = args['rom'] if 'rom' in args else None
    settings_dic: dict = args['applied_settings'] if 'applied_settings' in args else {}
    applied_settings = ScraperSettings.from_settings_dict(settings_dic)

    if scraped_rom_data is None:
        return

    scraped_rom = ROMObj(scraped_rom_data)
    rom_collection_ids = []
    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        romcollection_repository = ROMCollectionRepository(uow)
        rom_repository = ROMsRepository(uow)

        rom_romcollections = romcollection_repository.find_romcollections_by_rom(rom_id)
        rom_collection_ids = [collection.get_id() for collection in rom_romcollections]

        rom = rom_repository.find_rom(rom_id)

        metadata_is_updated = applied_settings.scrape_metadata_policy != constants.SCRAPE_ACTION_NONE
        assets_are_updated = applied_settings.scrape_assets_policy != constants.SCRAPE_ACTION_NONE

        metadata_to_update = applied_settings.metadata_IDs_to_scrape if metadata_is_updated else []
        assets_to_update = applied_settings.asset_IDs_to_scrape if assets_are_updated else []

        logger.debug('========================== Applied scraper settings ==========================')
        logger.debug('Metadata IDs:         {}'.format(', '.join(applied_settings.metadata_IDs_to_scrape)))
        logger.debug('Asset IDs:            {}'.format(', '.join(applied_settings.asset_IDs_to_scrape)))
        logger.debug('Overwrite existing:')
        logger.debug(' - Metadata           {}'.format('Yes' if applied_settings.overwrite_existing_meta else 'No'))
        logger.debug(' - Assets             {}'.format('Yes' if applied_settings.overwrite_existing_assets else 'No'))
        logger.debug('Metadata updated:     {}'.format('Yes' if metadata_is_updated else 'No'))
        logger.debug('Assets updated:       {}'.format('Yes' if assets_are_updated else 'No'))

        rom.update_with(scraped_rom,
                        metadata_to_update,
                        assets_to_update,
                        overwrite_existing_metadata=applied_settings.overwrite_existing_meta,
                        overwrite_existing_assets=applied_settings.overwrite_existing_assets,
                        update_scanned_data=not applied_settings.ignore_scrap_title)
        #  rom_obj.scraped_with(scraper_id)

        rom_repository.update_rom(rom)
        uow.commit()

    kodi.notify(kodi.translate(41009).format(rom.get_name()))

    if rom.get_scanned_by():
        AppMediator.async_cmd('RENDER_SOURCE_VIEW', {'source_id': rom.get_scanned_by()})
    else:
        AppMediator.async_cmd('RENDER_SOURCES_VIEW')

    for collection_id in rom_collection_ids:
        AppMediator.async_cmd('RENDER_ROMCOLLECTION_VIEW', {'romcollection_id': collection_id})

    if metadata_is_updated:
        AppMediator.async_cmd('RENDER_VCATEGORY_VIEWS')

    kodi.dialog_OK(
        kodi.translate(44127).format(
            rom.get_name()
        ),
        kodi.translate(44128)
    )

    return True


