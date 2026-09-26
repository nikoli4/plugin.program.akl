# -*- coding: utf-8 -*-
#
# Advanced Kodi Launcher Revival: Setup / New System Wizard
#

from __future__ import unicode_literals
from __future__ import division

import logging
import collections
import json

from akl.utils import kodi, io
from akl import platforms, constants, settings
from resources.lib.domain import Source, ROMLauncherAddonFactory

from resources.lib.commands.mediator import AppMediator
from resources.lib import globals
from resources.lib.repositories import (
    UnitOfWork,
    ROMCollectionRepository,
    ROMsRepository,
    SourcesRepository,
    AklAddonRepository
)

# ...all imports...

def _filter_platforms(search_term):
    if not search_term:
        return list(platforms.AKL_platform_list)

    search_term = search_term.strip().lower()

    return [
        platform
        for platform in platforms.AKL_platform_list
        if search_term in platform.lower()
    ]


logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


SETUP_WIZARD = 'SETUP_WIZARD'
PROCESS_SCRAPE_QUEUE = 'PROCESS_SCRAPE_QUEUE'

@AppMediator.register(SETUP_WIZARD)
def cmd_setup_wizard(args):
    logger.debug('SETUP_WIZARD: Starting setup wizard')

    if args.get('setup_wizard_continue', False):
        logger.info(
            'SETUP_WIZARD: Continuing directly with another system.'
        )
        _setup_new_system(args)
        return

    options = collections.OrderedDict()
    options['NEW_SYSTEM'] = kodi.translate(44056)
    options['EXISTING_SYSTEM'] = kodi.translate(44057)
    options['COMPONENTS'] = kodi.translate(44058)

    selected_option = kodi.OrdDictionaryDialog().select(
        kodi.translate(44042),
        options
    )

    if selected_option is None:
        logger.debug('SETUP_WIZARD: User cancelled.')
        return

    if selected_option == 'NEW_SYSTEM':
        args['setup_wizard_continue'] = False
        _setup_new_system(args)
        return

    if selected_option == 'EXISTING_SYSTEM':
        _show_existing_system_status()
        return

    if selected_option == 'COMPONENTS':
        _show_component_status()
        return

@AppMediator.register(PROCESS_SCRAPE_QUEUE)
def cmd_process_scrape_queue(args):
    logger.debug('SETUP_WIZARD: Processing scrape queue')

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
            'SETUP_WIZARD: Invalid scrape queue. '
            'Unable to begin queued scraping.'
        )
        return

    if not scrape_queue:
        logger.info(
            'SETUP_WIZARD: Scrape queue is empty.'
        )
        return

    romcollection_id = scrape_queue[0]

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
            'SETUP_WIZARD: Invalid prepared scrape data. '
            'Unable to begin queued scraping.'
        )
        return

    prepared_scrape = prepared_scrapes.get(
        romcollection_id,
        {}
    )

    system_scraper_id = prepared_scrape.get(
        'system_scraper_id'
    )
    
    system_scraper_settings = prepared_scrape.get(
        'system_scraper_settings'
    )

    if not system_scraper_id:
        logger.warning(
            f'SETUP_WIZARD: No prepared system scraper found '
            f'for collection "{romcollection_id}".'
        )
        return

    logger.info(
        f'SETUP_WIZARD: Beginning queued scrape for collection '
        f'"{romcollection_id}" (1 of {len(scrape_queue)}).'
    )

    kodi.set_windowprop(
        'AKL.SetupWizard.SystemScrapeCollectionID',
        romcollection_id
    )

    AppMediator.async_cmd(
        'SCRAPE_SYSTEM',
        {
            'romcollection_id': romcollection_id,
            'prepared_scraper_id': system_scraper_id,
            'prepared_scraper_settings': system_scraper_settings
        }
    )

def _setup_new_system(args):
    logger.debug('SETUP_WIZARD: Starting new system setup')
    logger.info(
        f'SETUP_WIZARD: New system context args: {args}'
    )

    continuing_setup = args.get(
        'setup_wizard_continue',
        False
    )

    kodi.clear_windowprops([
        'AKL.SetupWizard.SourceID',
        'AKL.SetupWizard.ScannerSourceID',
        'AKL.SetupWizard.CategoryID',
        'AKL.SetupWizard.CollectionID',
        'AKL.SetupWizard.SystemScrapeCollectionID',
        'AKL.SetupWizard.GameScrapeCollectionID'
    ])

    if not continuing_setup:
        kodi.clear_windowprops([
            'AKL.SetupWizard.ScrapeQueue',
            'AKL.SetupWizard.PreparedScrapes',
            'AKL.SetupWizard.PrepareIndex',
            'AKL.SetupWizard.SystemScrapeSettings',
            'AKL.SetupWizard.GameScrapeSettings',
            'AKL.SetupWizard.SystemScraperID',
            'AKL.SetupWizard.GameScraperID',
            'AKL.SetupWizard.ReuseScraperProviders',
            'AKL.SetupWizard.ReuseScrapeSettings'
        ])

        logger.info(
            'SETUP_WIZARD: Started new setup session and cleared '
            'previous wizard state.'
        )
    else:
        logger.info(
            'SETUP_WIZARD: Continuing existing setup session.'
        )

    category_id = args.get(
        'category_id',
        constants.VCATEGORY_ADDONROOT_ID
    )

    kodi.set_windowprop(
        'AKL.SetupWizard.CategoryID',
        category_id
    )
    
    logger.info(
        f'SETUP_WIZARD: Collection destination category set to '
        f'"{category_id}".'
    )
    
    # --- Step 1: Platform ---

    selected_platform = ''

    while not selected_platform:
        platform_options = collections.OrderedDict()
        platform_options['SEARCH'] = kodi.translate(44044)
        platform_options['BROWSE'] = kodi.translate(44045)

        platform_action = kodi.OrdDictionaryDialog().select(
            kodi.translate(44043),
            platform_options
        )

        if platform_action is None:
            logger.debug(
                'SETUP_WIZARD: New system setup cancelled during '
                'platform selection.'
            )
            return

        if platform_action == 'SEARCH':
            search_term = kodi.dialog_keyboard(
                kodi.translate(44044)
            )
            if search_term is None:
                logger.debug(
                    'SETUP_WIZARD: Platform search cancelled. '
                    'Returning to platform options.'
                )
                continue

            platform_list = _filter_platforms(search_term)

            if not platform_list:
                kodi.dialog_OK(
                    kodi.translate(44046).format(search_term),
                    kodi.translate(44043)
                )
                continue

            platform_title = kodi.translate(44055).format(search_term)

        else:
            platform_list = platforms.AKL_platform_list
            platform_title = kodi.translate(44043)

        wizard = kodi.WizardDialog_Selection(
            None,
            'platform',
            platform_title,
            platform_list
        )

        setup_data = {
            'platform': ''
        }

        setup_data = wizard.runWizard(setup_data)

        if setup_data is None:
            logger.debug(
                'SETUP_WIZARD: Platform list cancelled. '
                'Returning to platform options.'
            )
            continue

        selected_platform = setup_data.get('platform', '')

    if not selected_platform:
        logger.warning(
            'SETUP_WIZARD: Platform selection completed without a platform.'
        )
        return

    logger.info(
        f'SETUP_WIZARD: New system platform selected: '
        f'"{selected_platform}"'
    )

    # --- System / Source name ---

    name_wizard = kodi.WizardDialog_Keyboard(
        None,
        'name',
        kodi.translate(44047)
    )

    setup_data['name'] = selected_platform

    setup_data = name_wizard.runWizard(setup_data)

    if setup_data is None:
        logger.debug(
            'SETUP_WIZARD: New system setup cancelled during '
            'system name entry.'
        )
        return

    system_name = setup_data.get('name', '').strip()

    if not system_name:
        logger.warning(
            'SETUP_WIZARD: System name entry completed without a name.'
        )
        return

    logger.info(
        f'SETUP_WIZARD: New system name: "{system_name}"'
    )

    # --- Step 2: Scanner ---

    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)

    with uow:
        addon_repository = AklAddonRepository(uow)

        scanners = [
            *addon_repository.find_all_scanner_addons()
        ]

    if len(scanners) == 0:
        kodi.dialog_OK(
            kodi.translate(44048),
            kodi.translate(44049)
        )
        return

    scanners = sorted(
        scanners,
        key=lambda addon: addon.get_name().lower()
    )

    scanner_options = collections.OrderedDict()

    for scanner in scanners:
        scanner_options[scanner] = kodi.get_listitem(
            scanner.get_name(),
            scanner.get_addon_id()
        )

    selected_scanner = kodi.OrdDictionaryDialog().select(
        kodi.translate(44050),
        scanner_options,
        use_details=True
    )

    if selected_scanner is None:
        logger.debug(
            'SETUP_WIZARD: New system setup cancelled during scanner selection.'
        )
        return

    setup_data['scanner_id'] = selected_scanner.get_id()
    setup_data['scanner_addon_id'] = selected_scanner.get_addon_id()
    setup_data['scanner_name'] = selected_scanner.get_name()

    logger.info(
        f'SETUP_WIZARD: New system scanner selected: '
        f'"{selected_scanner.get_name()}" '
        f'({selected_scanner.get_addon_id()})'
    )

    # --- Step 3: Source artwork/assets folder ---

    assets_wizard = kodi.WizardDialog_FileBrowse(
        None,
        'assets_path',
        kodi.translate(44051),
        0,
        ''
    )

    setup_data['assets_path'] = settings.getSetting(
        'setup_default_artwork_root'
    )

    setup_data = assets_wizard.runWizard(setup_data)

    if setup_data is None:
        logger.debug(
            'SETUP_WIZARD: New system setup cancelled during '
            'artwork/assets folder selection.'
        )
        return

    selected_assets_parent = setup_data.get('assets_path', '')

    if not selected_assets_parent:
        logger.warning(
            'SETUP_WIZARD: Artwork/assets folder selection '
            'completed without a path.'
        )
        return

    assets_parent_FN = io.FileName(
        selected_assets_parent,
        isdir=True
    )

    assets_path_FN = assets_parent_FN.pjoin(
        system_name,
        isdir=True
    )

    selected_assets_path = assets_path_FN.getPath()

    logger.info(
        f'SETUP_WIZARD: Artwork/assets parent selected: '
        f'"{selected_assets_parent}"'
    )

    logger.info(
        f'SETUP_WIZARD: System artwork/assets root: '
        f'"{selected_assets_path}"'
    )

    logger.info(
        f'SETUP_WIZARD: New system artwork/assets folder selected: '
        f'"{selected_assets_path}"'
    )

    # --- Step 4: Create Source ---

    source = Source(None, selected_scanner)

    source_data = source.get_data_dic()
    source_data['platform'] = selected_platform
    source_data['name'] = system_name
    source_data['assets_path'] = selected_assets_path

    source.import_data_dic(source_data)

    source.set_assets_root_path(
        assets_path_FN,
        constants.ROM_ASSET_ID_LIST,
        create_default_subdirectories=True
    )

    platform = platforms.get_AKL_platform(selected_platform)
    source.set_box_sizing(platform.default_box_size)
    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)

    with uow:
        source_repository = SourcesRepository(uow)
        source_repository.insert_source(source)
        uow.commit()

    AppMediator.async_cmd(
        'RENDER_SOURCES_VIEW',
        {}
    )

    logger.info(
        f'SETUP_WIZARD: Created source '
        f'"{source.get_name()}" ({source.get_id()})'
    )

    kodi.dialog_OK(
        kodi.translate(44052).format(
            selected_platform,
            selected_scanner.get_name(),
            selected_assets_path,
            source.get_id()
        ),
        kodi.translate(44049)
    )

    # --- Step 5: Launcher provider ---

    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)

    with uow:
        addon_repository = AklAddonRepository(uow)

        launcher_addons = [
            *addon_repository.find_all_launcher_addons()
        ]

    if len(launcher_addons) == 0:
        kodi.dialog_OK(
            kodi.translate(44053),
            kodi.translate(44049)
        )
        return

    launcher_addons = sorted(
        launcher_addons,
        key=lambda addon: addon.get_name().lower()
    )

    launcher_options = collections.OrderedDict()

    for launcher_addon in launcher_addons:
        launcher_options[launcher_addon] = kodi.get_listitem(
            launcher_addon.get_name(),
            launcher_addon.get_addon_id()
        )

    selected_launcher_addon = kodi.OrdDictionaryDialog().select(
        kodi.translate(44054),
        launcher_options,
        use_details=True
    )

    if selected_launcher_addon is None:
        logger.debug(
            'SETUP_WIZARD: New system setup cancelled during '
            'launcher provider selection.'
        )
        return

    logger.info(
        f'SETUP_WIZARD: Launcher provider selected: '
        f'"{selected_launcher_addon.get_name()}" '
        f'({selected_launcher_addon.get_addon_id()})'
    )

    launcher = ROMLauncherAddonFactory.create(
        selected_launcher_addon,
        {}
    )

    kodi.set_windowprop(
        'AKL.SetupWizard.SourceID',
        source.get_id()
    )

    logger.info(
        f'SETUP_WIZARD: Set launcher continuation marker for '
        f'source "{source.get_id()}".'
    )

    default_emulators_root = settings.getSetting(
        'setup_default_emulators_root'
    )

    if default_emulators_root:
        kodi.set_windowprop(
            'AKL.SetupWizard.DefaultEmulatorsRoot',
            default_emulators_root
        )

        logger.info(
            f'SETUP_WIZARD: Set default Emulators root for launcher '
            f'configuration: "{default_emulators_root}".'
        )

    launcher.configure({
        'entity_type': constants.OBJ_SOURCE,
        'entity_id': source.get_id(),
        'system_name': source.get_name()
    })

    logger.info(
        f'SETUP_WIZARD: Started launcher configuration for '
        f'source "{source.get_name()}".'
    )

    return

def _show_component_status():
    while True:
        uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)

        with uow:
            addon_repository = AklAddonRepository(uow)

            scanners = [
                *addon_repository.find_all_scanner_addons()
            ]

            scrapers = [
                *addon_repository.find_all_scraper_addons()
            ]

            launchers = [
                *addon_repository.find_all_launcher_addons()
            ]

        logger.info(
            f'SETUP_WIZARD: Component status: '
            f'scanners={len(scanners)}, '
            f'scrapers={len(scrapers)}, '
            f'launchers={len(launchers)}'
        )

        options = collections.OrderedDict()

        options['SCANNERS'] = kodi.get_listitem(
            kodi.translate(44059),
            kodi.translate(44062).format(len(scanners))
            if len(scanners) > 0
            else kodi.translate(44063)
        )

        options['SCRAPERS'] = kodi.get_listitem(
            kodi.translate(44060),
            kodi.translate(44062).format(len(scrapers))
            if len(scrapers) > 0
            else kodi.translate(44063)
        )

        options['LAUNCHERS'] = kodi.get_listitem(
            kodi.translate(44061),
            kodi.translate(44062).format(len(launchers))
            if len(launchers) > 0
            else kodi.translate(44063)
        )

        options['REFRESH'] = kodi.get_listitem(
            kodi.translate(44064),
            kodi.translate(44065)
        )

        selected_option = kodi.OrdDictionaryDialog().select(
            kodi.translate(44066),
            options,
            use_details=True
        )

        if selected_option is None:
            return

        if selected_option == 'SCANNERS':
            _show_component_list(
                kodi.translate(44059),
                scanners
            )
            continue

        if selected_option == 'SCRAPERS':
            _show_component_list(
                kodi.translate(44060),
                scrapers
            )
            continue

        if selected_option == 'LAUNCHERS':
            _show_component_list(
                kodi.translate(44061),
                launchers
            )
            continue

        if selected_option == 'REFRESH':
            AppMediator.sync_cmd(
                'SCAN_FOR_ADDONS',
                {}
            )
            continue

def _show_component_list(title, addons):
    if len(addons) == 0:
        kodi.dialog_OK(
            kodi.translate(44067),
            title
        )
        return

    addons = sorted(
        addons,
        key=lambda addon: addon.get_name().lower()
    )

    options = collections.OrderedDict()

    for addon in addons:
        options[addon.get_id()] = kodi.get_listitem(
            addon.get_name(),
            kodi.translate(44068).format(
                addon.get_addon_id(),
                addon.get_version()
            )
        )

    kodi.OrdDictionaryDialog().select(
        title,
        options,
        use_details=True
    )

def _show_existing_system_status():
    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)

    with uow:
        collection_repository = ROMCollectionRepository(uow)
        roms_repository = ROMsRepository(uow)
        source_repository = SourcesRepository(uow)

        romcollections = [
            *collection_repository.find_all_romcollections()
        ]

        if len(romcollections) == 0:
            kodi.dialog_OK(
                kodi.translate(44069),
                kodi.translate(44042)
            )
            return

        romcollections = sorted(
            romcollections,
            key=lambda collection: collection.get_name().lower()
        )

        options = collections.OrderedDict()

        for romcollection in romcollections:
            options[romcollection] = romcollection.get_name()

        selected_collection = kodi.OrdDictionaryDialog().select(
            kodi.translate(44070),
            options
        )

        if selected_collection is None:
            return

        # Reload the selected collection as a complete object.
        # find_all_romcollections() does not populate launcher associations.
        selected_collection = collection_repository.find_romcollection(
            selected_collection.get_id()
        )

        roms = [
            *roms_repository.find_roms_by_romcollection(
                selected_collection
            )
        ]
        # Import rules define which Source(s) this collection is configured
        # to import ROMs from.
        import_rulesets = [
            *collection_repository.find_import_rules_by_collection(
                selected_collection
            )
        ]

        configured_sources = []

        for ruleset in import_rulesets:
            source_id = ruleset.get_source_id()

            if source_id:
                source = source_repository.find(source_id)

                if source is not None:
                    configured_sources.append(source)

        platform = selected_collection.get_platform()
        platform = platform if platform else kodi.translate(44071)

        # --- Source / Scanner status ---

        if len(configured_sources) == 0:
            source_status = kodi.translate(44071)
            scanner_status = kodi.translate(44071)
            source_rom_status = '0'
            last_scan_status = kodi.translate(44072)

        elif len(configured_sources) == 1:
            source = configured_sources[0]

            source_status = source.get_name()
            scanner_status = source.get_addon_name()
            source_rom_status = str(source.num_roms())

            last_scan = source.get_last_scan_timestamp()

            if last_scan:
                last_scan_status = str(last_scan)
            elif source.num_roms() > 0:
                last_scan_status = kodi.translate(44073)
            else:
                last_scan_status = kodi.translate(44072)

        else:
            source_status = kodi.translate(44075).format(
                len(configured_sources)
            )

            scanner_names = sorted(
                set(source.get_addon_name() for source in configured_sources)
            )
            scanner_status = ', '.join(scanner_names)

            source_rom_status = str(
                sum(source.num_roms() for source in configured_sources)
            )

            last_scan_status = kodi.translate(44074)
            
        # --- Import rules status ---

        if len(import_rulesets) == 0:
            import_rules_status = kodi.translate(44071)

        elif len(import_rulesets) == 1:
            ruleset = import_rulesets[0]

            if len(ruleset.get_rules()) == 0:
                import_rules_status = kodi.translate(44076)
            else:
                import_rules_status = kodi.translate(44077).format(
                    len(ruleset.get_rules())
                )

        else:
            import_rules_status = kodi.translate(44078).format(
                len(import_rulesets)
            )


        # --- Launcher status ---

        launchers = selected_collection.get_launchers()

        if len(launchers) == 0:
            launcher_status = kodi.translate(44071)
        else:
            default_launcher = selected_collection.get_default_launcher()

            if default_launcher is not None:
                launcher_status = default_launcher.get_name()
            else:
                launcher_status = kodi.translate(44079).format(
                    len(launchers)
                )


        logger.info(
            f'SETUP_WIZARD: Status for "{selected_collection.get_name()}": '
            f'platform="{platform}", '
            f'collection_roms={len(roms)}, '
            f'source="{source_status}", '
            f'scanner="{scanner_status}", '
            f'source_roms="{source_rom_status}", '
            f'import_rules="{import_rules_status}", '
            f'launcher="{launcher_status}"'
        )

        status_options = collections.OrderedDict()

        status_options['PLATFORM'] = kodi.get_listitem(
            kodi.translate(44080),
            platform
        )

        status_options['SOURCE'] = kodi.get_listitem(
            kodi.translate(44081),
            source_status
        )

        status_options['SCANNER'] = kodi.get_listitem(
            kodi.translate(44082),
            scanner_status
        )

        status_options['SCAN'] = kodi.get_listitem(
            kodi.translate(44083),
            kodi.translate(44087).format(
                source_rom_status,
                last_scan_status
            )
        )

        status_options['IMPORT_RULES'] = kodi.get_listitem(
            kodi.translate(44084),
            import_rules_status
        )

        status_options['COLLECTION'] = kodi.get_listitem(
            kodi.translate(44085),
            kodi.translate(44088).format(len(roms))
        )

        status_options['LAUNCHER'] = kodi.get_listitem(
            kodi.translate(44086),
            launcher_status
        )

        selected_status = kodi.OrdDictionaryDialog().select(
            kodi.translate(44089).format(
                selected_collection.get_name()
            ),
            status_options,
            use_details=True
        )

        if selected_status is None:
            return

        kodi.dialog_OK(
            kodi.translate(44090),
            kodi.translate(44042)
        )