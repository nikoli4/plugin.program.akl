# -*- coding: utf-8 -*-
#
# Advanced Kodi Launcher: Commands (romcollection roms management)
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
import json

from akl import constants
from akl.utils import kodi

from resources.lib.commands.mediator import AppMediator
from resources.lib import globals
from resources.lib.repositories import UnitOfWork, ROMCollectionRepository, ROMsRepository, SourcesRepository
from resources.lib.domain import g_assetFactory, RuleSet, Rule, ROM, RuleOperator, Source

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------------------------------
# ROMCollection ROM management.
# -------------------------------------------------------------------------------------------------

# --- Submenu menu command ---
@AppMediator.register('ROMCOLLECTION_MANAGE_ROMS')
def cmd_manage_roms(args):
    logger.debug('ROMCOLLECTION_MANAGE_ROMS: cmd_manage_roms() SHOW MENU')
    romcollection_id: str = args['romcollection_id'] if 'romcollection_id' in args else None

    if romcollection_id is None:
        logger.warning('cmd_manage_roms(): No romcollection id supplied.')
        kodi.notify_warn(kodi.translate(40951))
        return

    selected_option = None
    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        repository = ROMCollectionRepository(uow)
        romcollection = repository.find_romcollection(romcollection_id)

    has_roms = romcollection.has_roms()

    options = collections.OrderedDict()
    options['UPDATE_ROMCOLLECTION'] = kodi.translate(44151)
    options['SET_ROMS_DEFAULT_ARTWORK'] = kodi.translate(42044)
    options['IMPORT_ROMS'] = kodi.translate(42082)
    if has_roms:
        options['SCRAPE_ROMS'] = kodi.translate(42052)
        options['REMOVE_DEAD_ROMS_COLLECTION'] = kodi.translate(42047)
        options['CLEAR_ROMS'] = kodi.translate(42054)

    s = kodi.translate(41128).format(romcollection.get_name())
    selected_option = kodi.OrdDictionaryDialog().select(s, options)
    if selected_option is None:
        # >> Exits context menu
        logger.debug('ROMCOLLECTION_MANAGE_ROMS: cmd_manage_roms() Selected None. Closing context menu')
        if 'scraper_settings' in args:
            del args['scraper_settings']
        AppMediator.sync_cmd('EDIT_ROMCOLLECTION', args)
        return

    # >> Execute subcommand. May be atomic, maybe a submenu.
    logger.debug('ROMCOLLECTION_MANAGE_ROMS: cmd_manage_roms() Selected {}'.format(selected_option))
    AppMediator.sync_cmd(selected_option, args)

# --- Scan collection sources and then import newly discovered ROMs by ruleset ---
@AppMediator.register('UPDATE_ROMCOLLECTION')
def cmd_update_romcollection(args):
    romcollection_id: str = args['romcollection_id'] if 'romcollection_id' in args else None

    if romcollection_id is None:
        logger.warning('UPDATE_ROMCOLLECTION: No ROM collection id supplied.')
        kodi.notify_warn(kodi.translate(40951))
        return

    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        source_repository = SourcesRepository(uow)

        # Use AKL's existing collection/source relationship. This is also used
        # by the collection-level ROM scraping workflow.
        sources = list(
            source_repository.find_sources_by_collection(romcollection_id)
        )

        # Preserve repository order while protecting against duplicate sources.
        source_ids = []
        for source in sources:
            source_id = source.get_id()
            if source_id and source_id not in source_ids:
                source_ids.append(source_id)

    if not source_ids:
        logger.warning(
            'UPDATE_ROMCOLLECTION: No sources available for collection "{}".'.format(
                romcollection_id
            )
        )
        kodi.notify_warn('No ROM sources are available to update this collection.')
        return

    logger.info(
        'UPDATE_ROMCOLLECTION: Starting update for collection "{}" using {} source(s).'.format(
            romcollection_id,
            len(source_ids)
        )
    )

    # The external ROM scanner is asynchronous. Store enough state for
    # cmd_store_scanned_roms() to continue with the next source when the
    # current scan completes.
    kodi.set_windowprop(
        'AKL.UpdateCollection.CollectionID',
        romcollection_id
    )
    kodi.set_windowprop(
        'AKL.UpdateCollection.SourceQueue',
        json.dumps(source_ids)
    )

    # Start the first source. The scanner callback will advance the queue.
    AppMediator.async_cmd(
        'SCAN_ROMS',
        {
            'source_id': source_ids[0],
            'force': True
        }
    )


# --- Choose default ROMs assets/artwork ---
@AppMediator.register('SET_ROMS_DEFAULT_ARTWORK')
def cmd_set_roms_default_artwork(args):
    romcollection_id: str = args['romcollection_id'] if 'romcollection_id' in args else None

    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        repository = ROMCollectionRepository(uow)
        romcollection = repository.find_romcollection(romcollection_id)

        # --- Build Dialog.select() list ---
        default_assets_list = romcollection.get_ROM_mappable_asset_list()
        options = collections.OrderedDict()
        for default_asset_info in default_assets_list:
            # >> Label is the string 'Choose asset for XXXX (currently YYYYY)'
            mapped_asset_info = romcollection.get_ROM_asset_mapping(default_asset_info)
            # --- Append to list of ListItems ---
            options[default_asset_info] = kodi.translate(42055).format(
                kodi.translate(default_asset_info.name_id),
                kodi.translate(mapped_asset_info.name_id))

        dialog = kodi.OrdDictionaryDialog()
        selected_asset_info = dialog.select(kodi.translate(41077).format("ROM"), options)

        if selected_asset_info is None:
            # >> Return to parent menu.
            logger.debug('Main selected NONE. Returning to parent menu.')
            AppMediator.sync_cmd('ROMCOLLECTION_MANAGE_ROMS', args)
            return

        logger.debug(f'Main select() returned {selected_asset_info.name}')
        mapped_asset_info = romcollection.get_ROM_asset_mapping(selected_asset_info)
        mappable_asset_list = g_assetFactory.get_asset_list_by_IDs(constants.ROM_ASSET_ID_LIST, 'image')
        logger.debug(f'{selected_asset_info.name} currently is mapped to {mapped_asset_info.name}')

        # --- Create ListItems ---
        options = collections.OrderedDict()
        for mappable_asset_info in mappable_asset_list:
            # >> Label is the asset name (Icon, Fanart, etc.)
            options[mappable_asset_info] = kodi.translate(mappable_asset_info.name_id)

        dialog = kodi.OrdDictionaryDialog()
        dialog_title_str = kodi.translate(41078).format(romcollection.get_object_name(),
                                                        kodi.translate(selected_asset_info.name_id))
        new_selected_asset_info = dialog.select(dialog_title_str, options, mapped_asset_info)

        if new_selected_asset_info is None:
            # >> Return to this method recursively to previous menu.
            logger.debug('Mapable selected NONE. Returning to previous menu.')
            AppMediator.sync_cmd('ROMCOLLECTION_MANAGE_ROMS', args)
            return

        logger.debug(f'Mapable selected {new_selected_asset_info.name}.')
        romcollection.set_mapped_ROM_asset(selected_asset_info, new_selected_asset_info)
        kodi.notify(kodi.translate(40983).format(
            romcollection.get_object_name(),
            kodi.translate(selected_asset_info.name_id),
            kodi.translate(new_selected_asset_info.name_id)
        ))

        repository.update_romcollection(romcollection)
        uow.commit()
        AppMediator.async_cmd('RENDER_ROMCOLLECTION_VIEW', {'romcollection_id': romcollection.get_id()})
        AppMediator.async_cmd('RENDER_CATEGORY_VIEW', {'category_id': romcollection.get_parent_id()})

    AppMediator.sync_cmd('SET_ROMS_DEFAULT_ARTWORK', {
        'romcollection_id': romcollection.get_id(),
        'selected_asset': selected_asset_info.id})


@AppMediator.register('IMPORT_ROMS')
def cmd_import_roms(args):
    romcollection_id: str = args['romcollection_id'] if 'romcollection_id' in args else None

    selected_option = None
    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        repository = ROMCollectionRepository(uow)
        romcollection = repository.find_romcollection(romcollection_id)
        import_rules = repository.find_import_rules_by_collection(romcollection)

        options = collections.OrderedDict()
        for import_rule in import_rules:
            options[import_rule.get_ruleset_id()] = kodi.get_listitem(
                label=kodi.translate(41174).format(import_rule.get_source_name()),
                label2=f"{import_rule.get_rules_description()}",
                art={'icon': 'DefaultPlaylist.png'})

        options['NEW_IMPORT_RULESET'] = kodi.get_listitem(label=kodi.translate(40921), label2='',
                                                          art={'icon': 'DefaultAddSource.png'})

    s = kodi.translate(41130).format(romcollection.get_name())
    selected_option = kodi.OrdDictionaryDialog().select(s, options, use_details=True)
    if selected_option is None:
        # >> Exits context menu
        logger.debug('IMPORT_ROMS: Selected None. Closing context menu')
        AppMediator.sync_cmd('ROMCOLLECTION_MANAGE_ROMS', args)
        return

    if selected_option == 'NEW_IMPORT_RULESET':
        AppMediator.sync_cmd(selected_option, args)
        return

    logger.debug(f'IMPORT_ROMS: Selected set {selected_option}')
    args['ruleset_id'] = selected_option
    AppMediator.sync_cmd('EDIT_IMPORT_RULESET', args)


@AppMediator.register('NEW_IMPORT_RULESET')
def cmd_new_import_ruleset(args):
    romcollection_id: str = args['romcollection_id'] if 'romcollection_id' in args else None

    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        repository = ROMCollectionRepository(uow)
        romcollection = repository.find_romcollection(romcollection_id)

        selected_source = _select_source_for_rules(uow)
        if selected_source is None:
            # >> Exits context menu
            logger.debug('NEW_IMPORT_RULESET: No source selected. Closing context menu')
            AppMediator.sync_cmd('IMPORT_ROMS', args)
            return

        logger.debug(f'NEW_IMPORT_RULESET: Selected source {selected_source.get_id()}')

        ruleset = RuleSet()
        ruleset.apply_source(selected_source)

        repository.add_ruleset_to_romcollection(romcollection.get_id(), ruleset)
        uow.commit()

    args['ruleset_id'] = ruleset.get_ruleset_id()
    AppMediator.sync_cmd('EDIT_IMPORT_RULESET', args)


@AppMediator.register('EDIT_IMPORT_RULESET')
def cmd_edit_import_ruleset(args):
    romcollection_id: str = args['romcollection_id'] if 'romcollection_id' in args else None
    ruleset_id: str = args['ruleset_id'] if 'ruleset_id' in args else None

    selected_option = None
    next_command = None
    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        repository = ROMCollectionRepository(uow)
        ruleset = repository.find_ruleset(ruleset_id)

        options = collections.OrderedDict()
        options["EXECUTE_RULESET"] = kodi.get_listitem(kodi.translate(42089), "",
                                                       art={'icon': 'DefaultAddonsUpdates.png'})
        options["SET_RULESET_SOURCE"] = kodi.get_listitem(kodi.translate(42506), ruleset.get_source_name(),
                                                          art={'icon': 'DefaultPlaylist.png'})
        options["CHANGE_RULESET_OPERATOR"] = kodi.get_listitem(kodi.translate(41060), ruleset.get_set_operator_str(),
                                                               art={'icon': 'DefaultMimetypeInfo.png'})
        for rule in ruleset.get_rules():
            options[rule.get_id()] = kodi.get_listitem(kodi.translate(42511), rule.get_description(),
                                                       art={'icon': 'DefaultScript.png'})
        options["ADD_RULE_TO_RULESET"] = kodi.get_listitem(label=kodi.translate(42086), label2='',
                                                           art={'icon': 'DefaultAddSource.png'})
        if ruleset.has_rules():
            options["REMOVE_ALL_RULES"] = kodi.get_listitem(kodi.translate(41173), kodi.translate(41189).format(
                                                            ruleset.get_rules_shortdescription()))
        options["REMOVE_RULESET"] = kodi.get_listitem(kodi.translate(41193), label2='')

        s = kodi.translate(41184)
        selected_option = kodi.OrdDictionaryDialog().select(s, options, use_details=True)
        if selected_option is None:
            # >> Exits context menu
            logger.debug('EDIT_IMPORT_RULESET: No action selected. Closing context menu')
            args.pop('ruleset_id')
            next_command = 'IMPORT_ROMS'

        elif selected_option == 'SET_RULESET_SOURCE':
            source = _select_source_for_rules(uow)
            if source:
                ruleset.apply_source(source)
                repository.update_ruleset_in_romcollection(romcollection_id, ruleset)
                uow.commit()
            next_command = 'EDIT_IMPORT_RULESET'

        elif selected_option == 'CHANGE_RULESET_OPERATOR':
            ruleset.change_operator()
            repository.update_ruleset_in_romcollection(romcollection_id, ruleset)
            uow.commit()
            kodi.notify(kodi.translate(41180))
            next_command = 'EDIT_IMPORT_RULESET'

        elif selected_option == 'REMOVE_ALL_RULES':
            if kodi.dialog_yesno(kodi.translate(41175)):
                ruleset.clear_rules()
                repository.delete_all_rules_from_ruleset(ruleset)
                uow.commit()
                kodi.notify(kodi.translate(41176))
            next_command = 'EDIT_IMPORT_RULESET'

        elif selected_option == 'REMOVE_RULESET':
            if kodi.dialog_yesno(kodi.translate(41194)):
                repository.delete_ruleset(ruleset)
                uow.commit()
                kodi.notify(kodi.translate(41195))
            next_command = 'IMPORT_ROMS'

        elif selected_option == 'EXECUTE_RULESET' or selected_option == 'ADD_RULE_TO_RULESET':
            next_command = selected_option

        else:
            args['rule_id'] = selected_option
            next_command = 'EDIT_RULE'

    AppMediator.sync_cmd(next_command, args)


@AppMediator.register('ADD_RULE_TO_RULESET')
def cmd_add_rule_to_ruleset(args):
    romcollection_id: str = args['romcollection_id'] if 'romcollection_id' in args else None
    ruleset_id: str = args['ruleset_id'] if 'ruleset_id' in args else None

    field_options = collections.OrderedDict()
    fields = ROM.get_fields_with_translations()
    for fieldkey, fieldname in fields.items():
        field_options[fieldkey] = kodi.translate(fieldname)

    operator_options = collections.OrderedDict()
    operator_options[RuleOperator.Equals] = kodi.translate(30918)
    operator_options[RuleOperator.NotEquals] = kodi.translate(30919)
    operator_options[RuleOperator.Contains] = kodi.translate(30920)
    operator_options[RuleOperator.DoesNotContain] = kodi.translate(30921)
    operator_options[RuleOperator.MoreThan] = kodi.translate(30922)
    operator_options[RuleOperator.LessThan] = kodi.translate(30923)

    wizard = kodi.WizardDialog_DictionarySelection(None, 'property', kodi.translate(41177), field_options)
    wizard = kodi.WizardDialog_DictionarySelection(wizard, 'operator', kodi.translate(41178), operator_options)
    wizard = kodi.WizardDialog_Keyboard(wizard, 'value', kodi.translate(41179))

    rule = Rule()
    rule.set_ruleset(ruleset_id)

    entity_data = rule.get_data_dic()
    entity_data = wizard.runWizard(entity_data)
    if entity_data is None:
        AppMediator.sync_cmd('EDIT_IMPORT_RULESET', args)
        return

    rule.import_data_dic(entity_data)
    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        repository = ROMCollectionRepository(uow)
        ruleset = repository.find_ruleset(ruleset_id)

        ruleset.add_rule(rule)
        repository.update_ruleset_in_romcollection(romcollection_id, ruleset)
        uow.commit()

    AppMediator.sync_cmd('EDIT_IMPORT_RULESET', args)
    kodi.notify(kodi.translate(41180))


@AppMediator.register('EDIT_RULE')
def cmd_edit_rule(args):
    romcollection_id: str = args['romcollection_id'] if 'romcollection_id' in args else None
    ruleset_id: str = args['ruleset_id'] if 'ruleset_id' in args else None
    rule_id: str = args['rule_id'] if 'rule_id' in args else None

    dialog = kodi.ListDialog()
    selected_action = dialog.select(kodi.translate(41182), [
        kodi.translate('42087'),
        kodi.translate('42088')
    ])

    field_options = collections.OrderedDict()
    fields = ROM.get_fields_with_translations()
    for fieldkey, fieldname in fields.items():
        field_options[fieldkey] = kodi.translate(fieldname)

    operator_options = collections.OrderedDict()
    operator_options[RuleOperator.Equals] = kodi.translate(30918)
    operator_options[RuleOperator.NotEquals] = kodi.translate(30919)
    operator_options[RuleOperator.Contains] = kodi.translate(30920)
    operator_options[RuleOperator.DoesNotContain] = kodi.translate(30921)
    operator_options[RuleOperator.MoreThan] = kodi.translate(30922)
    operator_options[RuleOperator.LessThan] = kodi.translate(30923)

    wizard = kodi.WizardDialog_DictionarySelection(None, 'property', kodi.translate(41177), field_options)
    wizard = kodi.WizardDialog_DictionarySelection(wizard, 'operator', kodi.translate(41178), operator_options)
    wizard = kodi.WizardDialog_Keyboard(wizard, 'value', kodi.translate(41179))

    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        repository = ROMCollectionRepository(uow)
        ruleset = repository.find_ruleset(ruleset_id)

        rule = ruleset.get_rule(rule_id)
        if rule is None:
            kodi.notify_error(kodi.translate(41181))
            return

        if selected_action == 1:
            repository.delete_rule_from_ruleset(ruleset, rule)
            uow.commit()

        if selected_action == 0:
            entity_data = rule.get_data_dic()
            entity_data = wizard.runWizard(entity_data)
            if entity_data is None:
                AppMediator.sync_cmd('EDIT_IMPORT_RULESET', args)
                return

            rule.import_data_dic(entity_data)
            repository.update_ruleset_in_romcollection(romcollection_id, ruleset)
            uow.commit()

    kodi.notify(kodi.translate(41180))
    AppMediator.sync_cmd('EDIT_IMPORT_RULESET', args)


def _select_source_for_rules(uow: UnitOfWork):
    src_repository = SourcesRepository(uow)
    sources = src_repository.find_all()

    options = collections.OrderedDict()
    for source in sources:
        options[source] = source.get_name()

    # All
    empty_source = Source()
    empty_source.set_id(None)
    empty_source.set_name(kodi.translate(42508))
    options[empty_source] = kodi.translate(42508)

    s = kodi.translate(41172)
    selected_option = kodi.OrdDictionaryDialog().select(s, options)
    return selected_option


@AppMediator.register('EXECUTE_RULESET')
def cmd_execute_ruleset(args):
    romcollection_id: str = args['romcollection_id'] if 'romcollection_id' in args else None
    ruleset_id: str = args['ruleset_id'] if 'ruleset_id' in args else None

    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        repository = ROMCollectionRepository(uow)
        roms_repository = ROMsRepository(uow)
        src_repository = SourcesRepository(uow)

        ruleset = repository.find_ruleset(ruleset_id)
        collection = repository.find_romcollection(romcollection_id)

        sources = []
        if ruleset.get_source_id() is None:
            sources = src_repository.find_all()
        else:
            sources.append(src_repository.find(ruleset.get_source_id()))

        for source in sources:
            kodi.notify(kodi.translate(41190).format(collection.get_name(), source.get_name()))

            roms_in_collection = roms_repository.find_roms_by_romcollection(collection)
            collection_rom_ids = [rom.get_id() for rom in roms_in_collection]
            roms = [*roms_repository.find_roms_by_source(source)]
            logger.info(f"Processing {len(roms)} ROMs for ruleset")
            counter = 0
            progress_dialog = kodi.ProgressDialog()
            progress_dialog.startProgress(kodi.translate(41185), num_steps=len(roms))
            for rom in roms:
                progress_dialog.incrementStep()
                if rom.get_id() in collection_rom_ids:
                    logger.debug(f"ROM {rom.get_name()} already in collection.Skipping")
                    continue

                if not ruleset.applies_to(rom):
                    continue

                logger.debug(f"Adding ROM {rom.get_name()} to ROM Collection {collection.get_name()}")
                repository.add_rom_to_romcollection(romcollection_id, rom.get_id())
                collection_rom_ids.append(rom.get_id())
                counter += 1

            progress_dialog.endProgress()
            progress_dialog.close()
        uow.commit()

    AppMediator.async_cmd('RENDER_ROMCOLLECTION_VIEW', {'romcollection_id': romcollection_id})
    kodi.notify(kodi.translate(41183).format(counter))
    AppMediator.sync_cmd('EDIT_IMPORT_RULESET', args)


@AppMediator.register('EXECUTE_ALL_RULESETS')
def cmd_execute_all_rulesets(args):
    romcollection_id: str = args['romcollection_id'] if 'romcollection_id' in args else None

    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        repository = ROMCollectionRepository(uow)
        roms_repository = ROMsRepository(uow)
        src_repository = SourcesRepository(uow)

        collection = repository.find_romcollection(romcollection_id)
        rulesets = [*repository.find_import_rules_by_collection(collection)]

        if not rulesets:
            kodi.notify_warn(kodi.translate(41191))
            return

        roms_in_collection = roms_repository.find_roms_by_romcollection(collection)
        collection_rom_ids = [rom.get_id() for rom in roms_in_collection]

        counter = 0
        for ruleset in rulesets:
            sources = []
            if ruleset.get_source_id() is None:
                sources = src_repository.find_all()
            else:
                sources.append(src_repository.find(ruleset.get_source_id()))

            for source in sources:
                kodi.notify(kodi.translate(41190).format(collection.get_name(), source.get_name()))

                roms = [*roms_repository.find_roms_by_source(source)]
                logger.info(f"Processing {len(roms)} ROMs for ruleset")
                set_counter = 0
                progress_dialog = kodi.ProgressDialog()
                progress_dialog.startProgress(kodi.translate(41185), num_steps=len(roms))
                for rom in roms:
                    progress_dialog.incrementStep()
                    if rom.get_id() in collection_rom_ids:
                        logger.debug(f"ROM {rom.get_name()} already in collection.Skipping")
                        continue

                    if not ruleset.applies_to(rom):
                        continue

                    logger.debug(f"Adding ROM {rom.get_name()} to ROM Collection {collection.get_name()}")
                    repository.add_rom_to_romcollection(romcollection_id, rom.get_id())
                    collection_rom_ids.append(rom.get_id())
                    set_counter += 1

                progress_dialog.endProgress()
                progress_dialog.close()
        counter += set_counter
        uow.commit()

    AppMediator.async_cmd(
        'RENDER_ROMCOLLECTION_VIEW',
        {'romcollection_id': romcollection_id}
    )

    kodi.notify(kodi.translate(41183).format(counter))

    setup_wizard_collection_id = kodi.get_windowprop(
        'AKL.SetupWizard.CollectionID'
    )

    if setup_wizard_collection_id == romcollection_id:
        logger.info(
            f'SETUP_WIZARD: ROM import completed for collection '
            f'"{romcollection_id}" with {counter} imported ROM(s).'
        )

        kodi.clear_windowprops([
            'AKL.SetupWizard.CollectionID'
        ])

        logger.info(
            f'SETUP_WIZARD: Cleared collection continuation marker '
            f'for "{romcollection_id}".'
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
                'SETUP_WIZARD: Invalid scrape queue found. '
                'Starting a new queue.'
            )
            scrape_queue = []

        if romcollection_id not in scrape_queue:
            scrape_queue.append(romcollection_id)

        kodi.set_windowprop(
            'AKL.SetupWizard.ScrapeQueue',
            json.dumps(scrape_queue)
        )

        logger.info(
            f'SETUP_WIZARD: Added collection "{romcollection_id}" '
            f'to scrape queue. Queue contains '
            f'{len(scrape_queue)} collection(s).'
        )

        setup_another = kodi.dialog_yesno(
            kodi.translate(44116),
            kodi.translate(44117)
        )

        if setup_another:
            logger.info(
                'SETUP_WIZARD: User selected Set Up Another System.'
            )

            AppMediator.async_cmd(
                'SETUP_WIZARD',
                {
                    'setup_wizard_continue': True
                }
            )
            return

        logger.info(
            'SETUP_WIZARD: User finished adding systems. '
            f'{len(scrape_queue)} collection(s) are queued for scraping.'
        )

        scrape_options = collections.OrderedDict()
        scrape_options['SCRAPE_ALL'] = kodi.translate(44118)
        scrape_options['CHOOSE'] = kodi.translate(44119)
        scrape_options['FINISH'] = kodi.translate(44120)

        selected_scrape_option = kodi.OrdDictionaryDialog().select(
            kodi.translate(44121),
            scrape_options
        )

        if selected_scrape_option is None:
            logger.info(
                'SETUP_WIZARD: User cancelled queued scraping menu. '
                'Preserving wizard scrape state.'
            )
            return

        if selected_scrape_option == 'SCRAPE_ALL':
            logger.info(
                'SETUP_WIZARD: User selected Scrape All Now.'
            )

            kodi.set_windowprop(
                'AKL.SetupWizard.PrepareIndex',
                '0'
            )

            first_collection_id = scrape_queue[0]

            logger.info(
                f'SETUP_WIZARD: Starting scrape preparation for '
                f'collection "{first_collection_id}".'
            )

            AppMediator.async_cmd(
                'PREPARE_WIZARD_SYSTEM_SCRAPE',
                {
                    'romcollection_id': first_collection_id
                }
            )
            return

        if selected_scrape_option == 'CHOOSE':
            logger.info(
                'SETUP_WIZARD: User selected Choose What to Scrape.'
            )

            collection_options = collections.OrderedDict()

            uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
            with uow:
                collection_repository = ROMCollectionRepository(uow)

                for queued_collection_id in scrape_queue:
                    romcollection = collection_repository.find_romcollection(
                        queued_collection_id
                    )

                    if romcollection is not None:
                        collection_options[queued_collection_id] = (
                            romcollection.get_name()
                        )

            selected_collections = kodi.MultiSelectDialog().select(
                kodi.translate(44122),
                collection_options,
                preselected=list(collection_options.keys())
            )

            if selected_collections is None:
                logger.info(
                    'SETUP_WIZARD: User cancelled system scrape selection.'
                )
                return

            if not selected_collections:
                logger.info(
                    'SETUP_WIZARD: User selected no systems for scraping.'
                )

                kodi.dialog_OK(
                    kodi.translate(44123),
                    kodi.translate(44121)
                )
                return

            scrape_queue = selected_collections

            kodi.set_windowprop(
                'AKL.SetupWizard.ScrapeQueue',
                json.dumps(scrape_queue)
            )

            logger.info(
                f'SETUP_WIZARD: Updated scrape queue with '
                f'{len(scrape_queue)} selected collection(s).'
            )

            kodi.set_windowprop(
                'AKL.SetupWizard.PrepareIndex',
                '0'
            )

            first_collection_id = scrape_queue[0]

            logger.info(
                f'SETUP_WIZARD: Starting scrape preparation for '
                f'collection "{first_collection_id}".'
            )

            AppMediator.async_cmd(
                'PREPARE_WIZARD_SYSTEM_SCRAPE',
                {
                    'romcollection_id': first_collection_id
                }
            )
            return

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
            'SETUP_WIZARD: User finished setup without '
            'starting queued scraping. Cleared wizard scrape state.'
        )

        AppMediator.sync_cmd(
            'SHOW_AKL_SETUP_COMPLETE',
            {}
        )

# --- Select multiple ROM collections for bulk scraping ---
@AppMediator.register('SCRAPE_SYSTEMS')
def cmd_scrape_systems(args):
    logger.info('SCRAPE_SYSTEMS: Starting bulk system scrape selection.')

    collection_options = collections.OrderedDict()

    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        collection_repository = ROMCollectionRepository(uow)

        for romcollection in collection_repository.find_all_romcollections():
            collection_options[romcollection.get_id()] = romcollection.get_name()

    if not collection_options:
        logger.warning('SCRAPE_SYSTEMS: No ROM collections are available.')
        kodi.notify_warn(kodi.translate(44154))
        return

    selected_collections = kodi.MultiSelectDialog().select(
        kodi.translate(44153),
        collection_options,
        preselected=list(collection_options.keys())
    )

    if selected_collections is None:
        logger.info('SCRAPE_SYSTEMS: User cancelled system selection.')
        return

    if not selected_collections:
        logger.info('SCRAPE_SYSTEMS: User selected no systems.')
        return

    logger.info(
        f'SCRAPE_SYSTEMS: User selected '
        f'{len(selected_collections)} collection(s): '
        f'{selected_collections}'
    )

    first_collection_id = selected_collections[0]

    logger.info(
        f'SCRAPE_SYSTEMS: Starting bulk scrape configuration using '
        f'collection "{first_collection_id}".'
    )

    AppMediator.async_cmd(
        'SCRAPE_SYSTEM',
        {
            'romcollection_id': first_collection_id,
            'bulk_system_scrape_queue': selected_collections
        }
    )


# --- Remove dead/missing ROMs from collection ---
@AppMediator.register('REMOVE_DEAD_ROMS_COLLECTION')
def cmd_remove_dead_roms_collection(args):
    romcollection_id: str = args['romcollection_id'] if 'romcollection_id' in args else None

    if romcollection_id is None:
        logger.warning('cmd_remove_dead_roms_collection(): No ROM collection id supplied.')
        kodi.notify_warn(kodi.translate(40951))
        return

    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        collection_repository = ROMCollectionRepository(uow)
        roms_repository = ROMsRepository(uow)

        romcollection = collection_repository.find_romcollection(romcollection_id)

        if romcollection is None:
            logger.warning(
                f'REMOVE_DEAD_ROMS_COLLECTION: ROM collection "{romcollection_id}" not found.'
            )
            return

        confirm_scan = kodi.dialog_yesno(
            kodi.translate(44124).format(
                romcollection.get_name()
            ),
            kodi.translate(44110)
        )

        if not confirm_scan:
            logger.info(
                f'REMOVE_DEAD_ROMS_COLLECTION: Scan cancelled for '
                f'collection "{romcollection.get_name()}".'
            )
            return

        roms = [*roms_repository.find_roms_by_romcollection(romcollection)]

        logger.info(
            f'REMOVE_DEAD_ROMS_COLLECTION: Checking {len(roms)} ROM(s) '
            f'in collection "{romcollection.get_name()}"'
        )

        if len(roms) == 0:
            kodi.dialog_OK(
                kodi.translate(44125),
                kodi.translate(44110)
            )
            return

        dead_roms = []

        for rom in roms:
            rom_path = rom.get_scanned_data_element('file')

            if not rom_path:
                logger.warning(
                    f'REMOVE_DEAD_ROMS_COLLECTION: ROM "{rom.get_name()}" '
                    f'has no scanned file path. Skipping.'
                )
                continue

            rom_file = rom.get_scanned_data_element_as_file('file')

            if not rom_file.exists():
                logger.info(
                    f'REMOVE_DEAD_ROMS_COLLECTION: Missing ROM '
                    f'"{rom.get_name()}" -> "{rom_file.getPath()}"'
                )
                dead_roms.append(rom)

        if len(dead_roms) == 0:
            logger.info(
                f'REMOVE_DEAD_ROMS_COLLECTION: Checked {len(roms)} ROM(s); '
                f'0 missing; nothing removed.'
            )

            kodi.dialog_OK(
                kodi.translate(44113).format(
                    len(roms)
                ),
                kodi.translate(44110)
            )
            return

        confirm_remove = kodi.dialog_yesno(
            kodi.translate(44114).format(
                len(roms),
                len(dead_roms)
            ),
            kodi.translate(44110)
        )

        if not confirm_remove:
            logger.info(
                f'REMOVE_DEAD_ROMS_COLLECTION: Found {len(dead_roms)} '
                f'missing ROM(s); user cancelled removal.'
            )
            return

        # Remember the affected source IDs before deleting the ROMs.
        source_ids = set()

        for rom in dead_roms:
            source_id = rom.get_scanned_by()
            if source_id:
                source_ids.add(source_id)

            logger.info(
                f'REMOVE_DEAD_ROMS_COLLECTION: Removing '
                f'"{rom.get_name()}" ({rom.get_id()})'
            )
            roms_repository.delete_rom(rom.get_id())

        uow.commit()

    logger.info(
        f'REMOVE_DEAD_ROMS_COLLECTION: Removed {len(dead_roms)} '
        f'missing ROM(s) from collection "{romcollection.get_name()}"'
    )

    kodi.notify(
        kodi.translate(44115).format(
            len(dead_roms),
            romcollection.get_name()
        )
    )

    AppMediator.async_cmd(
        'RENDER_ROMCOLLECTION_VIEW',
        {'romcollection_id': romcollection_id}
    )

    for source_id in source_ids:
        AppMediator.async_cmd(
            'RENDER_SOURCE_VIEW',
            {'source_id': source_id}
        )

    AppMediator.async_cmd('RENDER_VCATEGORY_VIEWS')

@AppMediator.register('CLEAR_ROMS')
def cmd_clear_roms(args):
    romcollection_id: str = args['romcollection_id'] if 'romcollection_id' in args else None

    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)
    with uow:
        collection_repository = ROMCollectionRepository(uow)
        roms_repository = ROMsRepository(uow)

        romcollection = collection_repository.find_romcollection(romcollection_id)
        roms = roms_repository.find_roms_by_romcollection(romcollection)

        # If collection is empty (no ROMs) do nothing
        num_roms = len([*roms])
        if num_roms == 0:
            kodi.dialog_OK(kodi.translate(41151))
            return

        # Confirm user wants to delete ROMs
        ret = kodi.dialog_yesno(kodi.translate(41142).format(romcollection.get_name(), num_roms))
        if not ret:
            return

        # --- If there is a No-Intro XML DAT configured remove it ---
        # TODO fix
        # romcollection.reset_nointro_xmldata()
        collection_repository.remove_all_roms_in_collection(romcollection_id)
        uow.commit()

    AppMediator.async_cmd('RENDER_ROMCOLLECTION_VIEW', {'romcollection_id': romcollection_id})
    AppMediator.async_cmd('RENDER_CATEGORY_VIEW', {'category_id': romcollection.get_parent_id()})
    kodi.notify(kodi.translate(40977))
