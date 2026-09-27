# -*- coding: utf-8 -*-
#
# Advanced Kodi Launcher Revival: First-Run Setup Assistant
#

from __future__ import unicode_literals
from __future__ import division

import logging
import collections

import xbmc

from akl import settings
from akl.utils import kodi

from resources.lib.commands.mediator import AppMediator


logger = logging.getLogger(__name__)


FIRST_RUN_SETUP = 'FIRST_RUN_SETUP'


def _get_component_status(addon_id):
    json_response = kodi.jsonrpc_query(
        'Addons.GetAddonDetails',
        {
            'addonid': addon_id,
            'properties': [
                'name',
                'version',
                'enabled'
            ]
        }
    )

    result = json_response.get('result', {})
    addon = result.get('addon')

    if not addon:
        return {
            'installed': False,
            'enabled': False,
            'name': addon_id,
            'version': ''
        }

    return {
        'installed': True,
        'enabled': addon.get('enabled', False),
        'name': addon.get('name', addon_id),
        'version': addon.get('version', '')
    }


@AppMediator.register(FIRST_RUN_SETUP)
def cmd_first_run_setup(args):
    logger.info('FIRST_RUN: Starting First-Run Setup Assistant.')

    options = collections.OrderedDict()
    options['START'] = kodi.translate(44091)
    options['NOT_NOW'] = kodi.translate(44092)
    options['DONT_ASK'] = kodi.translate(44093)

    selected_option = kodi.OrdDictionaryDialog().select(
        kodi.translate(44094),
        options
    )

    if selected_option is None:
        logger.info(
            'FIRST_RUN: Setup Assistant cancelled. '
            'First-run remains incomplete.'
        )
        return

    if selected_option == 'NOT_NOW':
        logger.info(
            'FIRST_RUN: User chose Not Now. '
            'First-run remains incomplete.'
        )
        return

    if selected_option == 'DONT_ASK':
        settings.setSetting(
            'first_run_completed',
            'true'
        )

        logger.info(
            'FIRST_RUN: User chose Don\'t Ask Again. '
            'First-run marked complete.'
        )
        return

    if selected_option == 'START':
        logger.info(
            'FIRST_RUN: User chose Start Setup.'
        )

        setup_data = {
            'roms_root': settings.getSetting(
                'setup_default_roms_root'
            ),
            'emulators_root': settings.getSetting(
                'setup_default_emulators_root'
            ),
            'artwork_root': settings.getSetting(
                'setup_default_artwork_root'
            )
        }

        wizard = kodi.WizardDialog_FileBrowse(
            None,
            'artwork_root',
            kodi.translate(44095),
            0,
            ''
        )

        wizard = kodi.WizardDialog_FileBrowse(
            wizard,
            'emulators_root',
            kodi.translate(44096),
            0,
            ''
        )

        wizard = kodi.WizardDialog_FileBrowse(
            wizard,
            'roms_root',
            kodi.translate(44097),
            0,
            ''
        )
        
        setup_data = wizard.runWizard(setup_data)

        if not setup_data:
            logger.info(
                'FIRST_RUN: Default path setup cancelled.'
            )
            return

        settings.setSetting(
            'setup_default_roms_root',
            setup_data.get('roms_root', '')
        )

        settings.setSetting(
            'setup_default_emulators_root',
            setup_data.get('emulators_root', '')
        )

        settings.setSetting(
            'setup_default_artwork_root',
            setup_data.get('artwork_root', '')
        )

        logger.info(
            'FIRST_RUN: Default setup paths saved.'
        )

        components = collections.OrderedDict([
            (
                'script.akl.defaults',
                'AKL Default Plugins'
            ),
            (
                'script.akl.steam',
                'Steam'
            ),
            (
                'script.akl.retroarchlauncher',
                'RetroArch Launcher'
            )
        ])

        scrapers = collections.OrderedDict([
            (
                'script.akl.screenscraper',
                'ScreenScraper'
            ),
            (
                'script.akl.tgdbscraper',
                'TheGamesDB'
            ),
            (
                'script.akl.mobygames',
                'MobyGames'
            ),
            (
                'script.akl.arcadedb',
                'ArcadeDB'
            ),
            (
                'script.akl.gamefaqs',
                'GameFAQs'
            ),
            (
                'script.akl.googlesearch',
                'Google Search'
            ),
            (
                'script.akl.steamgriddb',
                'SteamGridDB'
            ),
            (
                'script.akl.offlinescraper',
                'Offline Database'
            )
        ])
        
        skins = collections.OrderedDict([
            (
                'skin.arctic.zephyr.akl',
                'Arctic: Zephyr - Reloaded (AKL Edition)'
            )
        ])

        def _build_component_options(addons, recommended=None):
            options = collections.OrderedDict()
            preselected = []

            for addon_id, display_name in addons.items():
                status = _get_component_status(addon_id)

                if status['installed']:
                    if status['enabled']:
                        label = kodi.translate(44098).format(
                            display_name
                        )
                    else:
                        label = kodi.translate(44099).format(
                            display_name
                        )

                    preselected.append(addon_id)
                else:
                    label = display_name

                options[addon_id] = label

            if (
                recommended
                and recommended in options
                and recommended not in preselected
            ):
                preselected.append(recommended)

            return options, preselected

        def _build_skin_options(addons):
            options = collections.OrderedDict()

            for addon_id, display_name in addons.items():
                status = _get_component_status(addon_id)

                if status['installed']:
                    if status['enabled']:
                        label = kodi.translate(44098).format(
                            display_name
                        )
                    else:
                        label = kodi.translate(44099).format(
                            display_name
                        )
                else:
                    label = display_name

                options[addon_id] = label

            return options

        component_options, component_preselected = (
            _build_component_options(
                components,
                'script.akl.defaults'
            )
        )

        selected_components = kodi.MultiSelectDialog().select(
            kodi.translate(44100),
            component_options,
            preselected=component_preselected
        )

        if selected_components is None:
            logger.info(
                'FIRST_RUN: Component selection cancelled.'
            )
            return

        scraper_options, scraper_preselected = (
            _build_component_options(
                scrapers,
                'script.akl.screenscraper'
            )
        )

        selected_scrapers = kodi.MultiSelectDialog().select(
            kodi.translate(44101),
            scraper_options,
            preselected=scraper_preselected
        )

        if selected_scrapers is None:
            logger.info(
                'FIRST_RUN: Scraper selection cancelled.'
            )
            return

        skin_options = _build_skin_options(skins)

        selected_skins = kodi.MultiSelectDialog().select(
            kodi.translate(44140),
            skin_options,
            preselected=[]
        )

        if selected_skins is None:
            logger.info(
                'FIRST_RUN: Skin selection cancelled.'
            )
            return

        logger.info(
            'FIRST_RUN: Selected components: {}'.format(
                ', '.join(selected_components)
                if selected_components
                else '(none)'
            )
        )

        logger.info(
            'FIRST_RUN: Selected scrapers: {}'.format(
                ', '.join(selected_scrapers)
                if selected_scrapers
                else '(none)'
            )
        )

        logger.info(
            'FIRST_RUN: Selected skins: {}'.format(
                ', '.join(selected_skins)
                if selected_skins
                else '(none)'
            )
        )

        selected_addons = (
            selected_components
            + selected_scrapers
        )

        for addon_id in selected_addons:
            status = _get_component_status(addon_id)

            if status['installed']:
                continue

            logger.info(
                'FIRST_RUN: Installing component {}.'.format(
                    addon_id
                )
            )

            xbmc.executebuiltin(
                'InstallAddon({})'.format(addon_id),
                True
            )

            status = _get_component_status(addon_id)

            logger.info(
                'FIRST_RUN: Installation result for {}: '
                'installed={}, enabled={}, name="{}", version="{}"'.format(
                    addon_id,
                    status['installed'],
                    status['enabled'],
                    status['name'],
                    status['version']
                )
            )

        installed_selected_skins = []
        failed_skins = []

        for addon_id in selected_skins:
            status = _get_component_status(addon_id)

            if not status['installed']:
                logger.info(
                    'FIRST_RUN: Installing optional skin {}.'.format(
                        addon_id
                    )
                )

                xbmc.executebuiltin(
                    'InstallAddon({})'.format(addon_id),
                    True
                )

                status = _get_component_status(addon_id)

                logger.info(
                    'FIRST_RUN: Skin installation result for {}: '
                    'installed={}, enabled={}, name="{}", version="{}"'.format(
                        addon_id,
                        status['installed'],
                        status['enabled'],
                        status['name'],
                        status['version']
                    )
                )

            if status['installed']:
                installed_selected_skins.append(addon_id)
            else:
                failed_skins.append(addon_id)

        if failed_skins:
            logger.error(
                'FIRST_RUN: Failed to install selected skins: {}'.format(
                    ', '.join(failed_skins)
                )
            )

            kodi.dialog_OK(
                kodi.translate(44145),
                kodi.translate(44140)
            )

        # Verify Kodi exposes the current skin through lookandfeel.skin.
        if installed_selected_skins:
            current_skin_response = kodi.jsonrpc_query(
                'Settings.GetSettingValue',
                {
                    'setting': 'lookandfeel.skin'
                }
            )

            logger.info(
                'FIRST_RUN: Current Kodi skin setting: {}'.format(
                    current_skin_response
                )
            )

        logger.info(
            'FIRST_RUN: Scanning installed AKL components.'
        )

        AppMediator.sync_cmd(
            'SCAN_FOR_ADDONS',
            {}
        )

        logger.info(
            'FIRST_RUN: AKL component scan completed.'
        )

        finish_options = collections.OrderedDict()
        finish_options['SETUP_SYSTEM'] = kodi.translate(44102)
        finish_options['FINISH'] = kodi.translate(44103)

        selected_finish = kodi.OrdDictionaryDialog().select(
            kodi.translate(44104),
            finish_options
        )

        if selected_finish is None:
            logger.info(
                'FIRST_RUN: Finish selection cancelled. '
                'First-run remains incomplete.'
            )
            return

        settings.setSetting(
            'first_run_completed',
            'true'
        )

        logger.info(
            'FIRST_RUN: First-run setup marked complete.'
        )

        if selected_finish == 'SETUP_SYSTEM':
            logger.info(
                'FIRST_RUN: Starting Setup / New System Wizard.'
            )

            AppMediator.sync_cmd(
                'SETUP_WIZARD',
                {
                    'setup_wizard_continue': True
                }
            )

            return

        logger.info(
            'FIRST_RUN: Setup complete. Returning to AKL.'
        )

        AppMediator.sync_cmd(
            'SHOW_AKL_SETUP_COMPLETE',
            {}
        )


@AppMediator.register('SHOW_AKL_SETUP_COMPLETE')
def cmd_show_akl_setup_complete(args):
    """Show final AKL setup guidance after a completed setup workflow."""
    logger.info(
        'FIRST_RUN: Showing final AKL skin setup guidance.'
    )

    kodi.dialog_OK(
        kodi.translate(44148),
        kodi.translate(44104)
    )

    kodi.dialog_OK(
        kodi.translate(44149),
        kodi.translate(44104)
    )
