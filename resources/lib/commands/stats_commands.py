# -*- coding: utf-8 -*-




#




# Advanced Kodi Launcher: Commands (generating stats and counts)




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









from akl import constants




from akl.utils import kodi









from resources.lib.commands.mediator import AppMediator




from resources.lib import globals




from resources.lib.repositories import UnitOfWork, ROMsRepository









logger = logging.getLogger(__name__)














# -------------------------------------------------------------------------------------------------




# ROM stats




# -------------------------------------------------------------------------------------------------









@AppMediator.register('ROM_WAS_LAUNCHED')




def cmd_process_launching_of_rom(args):




    logger.debug('ROM_WAS_LAUNCHED: Processing that a ROM was launched')




    rom_id: str = args['rom_id'] if 'rom_id' in args else None




    if rom_id is None:




        logger.warning('No rom id supplied.')




        return









    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)




    with uow:




        repository = ROMsRepository(uow)




        rom = repository.find_rom(rom_id)









        rom.increase_launch_count()




        repository.update_rom(rom)









        uow.commit()




        logger.debug(f'ROM_WAS_LAUNCHED: Processed stats for ROM {rom.get_name()}')




        AppMediator.async_cmd('RENDER_VCOLLECTION_VIEW', {'vcollection_id': constants.VCOLLECTION_RECENT_ID})




        AppMediator.async_cmd('RENDER_VCOLLECTION_VIEW', {'vcollection_id': constants.VCOLLECTION_MOST_PLAYED_ID})














def _write_managed_launch_ack(launch_id, rom_id):



    """Atomically acknowledge completed managed launch bookkeeping."""



    import json



    import os



    import re



    import uuid



    import xbmcvfs







    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', launch_id):



        raise ValueError('Invalid managed launch ID')







    addon_data = xbmcvfs.translatePath(



        'special://profile/addon_data/plugin.program.akl/'



    )







    os.makedirs(addon_data, exist_ok=True)







    filename = 'managed_launch_ack_{}.json'.format(launch_id)



    final_path = os.path.join(addon_data, filename)



    temporary_path = final_path + '.' + uuid.uuid4().hex + '.tmp'







    payload = {



        'launch_id': launch_id,



        'rom_id': rom_id,



        'status': 'complete'



    }







    try:



        with open(temporary_path, 'w', encoding='utf-8') as handle:



            json.dump(payload, handle)



            handle.flush()



            os.fsync(handle.fileno())







        os.replace(temporary_path, final_path)



    finally:



        if os.path.exists(temporary_path):



            os.remove(temporary_path)







def _read_managed_launch_type(launch_id, rom_id):
    """Read a prepared managed configuration without executing the launcher."""
    import json
    import os
    import re
    import xbmcvfs

    if not isinstance(launch_id, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]{1,128}", launch_id
    ):
        return None

    if not isinstance(rom_id, str) or not rom_id:
        return None

    addon_data = xbmcvfs.translatePath(
        "special://profile/addon_data/plugin.program.akl/"
    )

    path = os.path.join(
        addon_data,
        "managed_launch_config_{}.json".format(launch_id)
    )

    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            payload = json.load(handle)
    except (OSError, ValueError, UnicodeError):
        return None

    if not isinstance(payload, dict):
        return None

    if payload.get("launch_id") != launch_id:
        return None

    if payload.get("rom_id") != rom_id:
        return None

    launch_type = payload.get("launch_type")

    if launch_type == "steam":
        app_id = payload.get("steam_app_id")

        if (
            isinstance(app_id, str)
            and re.fullmatch(r"[0-9]{1,20}", app_id)
            and int(app_id) > 0
            and payload.get("steam_launch_arguments") == []
            and "application" not in payload
            and "arguments" not in payload
        ):
            return "steam"

        return None

    if launch_type in (None, "emulator"):
        if (
            isinstance(payload.get("application"), str)
            and payload["application"].strip()
            and isinstance(payload.get("arguments"), list)
            and all(
                isinstance(argument, str)
                for argument in payload["arguments"]
            )
        ):
            return "emulator"

    return None


def _wait_for_managed_emulator_started(launch_id, rom_id, timeout=15, monitor=None):




    """Require matching emulator process creation before counting a launch."""




    import json




    import os




    import re




    import time




    import xbmcvfs









    if not isinstance(launch_id, str) or not re.fullmatch(




        r"[A-Za-z0-9_-]{1,128}", launch_id




    ):




        raise ValueError("Invalid managed launch ID")









    if not isinstance(rom_id, str) or not rom_id:




        raise ValueError("Invalid managed ROM ID")









    if timeout < 0:




        raise ValueError("Invalid managed startup timeout")









    addon_data = xbmcvfs.translatePath(




        "special://profile/addon_data/plugin.program.akl/"




    )









    path = os.path.join(




        addon_data,




        "managed_emulator_started_{}.json".format(launch_id)




    )









    deadline = time.monotonic() + timeout









    while True:




        try:




            with open(path, "r", encoding="utf-8-sig") as handle:




                payload = json.load(handle)




        except (OSError, ValueError, UnicodeError):




            payload = None









        if isinstance(payload, dict):




            pid = payload.get("pid")









            if (




                payload.get("launch_id") == launch_id




                and payload.get("rom_id") == rom_id




                and payload.get("status") == "started"




                and isinstance(pid, int)




                and not isinstance(pid, bool)




                and pid > 0




            ):




                return True









        remaining = deadline - time.monotonic()









        if remaining <= 0:




            return False









        interval = min(0.1, remaining)

        if monitor is not None:
            if monitor.waitForAbort(interval):
                return False
        else:
            time.sleep(interval)














def _validate_managed_steam_started(payload, launch_id, rom_id):



    """Validate a recorded Steam game startup without process operations."""



    import math



    import re







    if not isinstance(launch_id, str) or not re.fullmatch(



        r"[A-Za-z0-9_-]{1,128}", launch_id



    ):



        return False







    if not isinstance(rom_id, str) or not rom_id:



        return False







    if not isinstance(payload, dict):



        return False







    app_id = payload.get("steam_app_id")



    pid = payload.get("pid")



    timestamp = payload.get("timestamp")







    return (



        payload.get("launch_id") == launch_id



        and payload.get("rom_id") == rom_id



        and payload.get("status") == "started"



        and isinstance(app_id, str)



        and re.fullmatch(r"[0-9]{1,20}", app_id) is not None



        and int(app_id) > 0



        and isinstance(pid, int)



        and not isinstance(pid, bool)



        and pid > 0



        and isinstance(timestamp, (int, float))



        and not isinstance(timestamp, bool)



        and math.isfinite(timestamp)



        and timestamp > 0



    )











def _read_managed_steam_started(addon_data_dir, launch_id, rom_id):


    """Read and validate a managed Steam startup confirmation."""


    import json


    import os


    import re





    if not isinstance(addon_data_dir, str) or not addon_data_dir.strip():


        return None





    if not isinstance(launch_id, str) or not re.fullmatch(


        r"[A-Za-z0-9_-]{1,128}", launch_id


    ):


        return None





    if not isinstance(rom_id, str) or not rom_id:


        return None





    path = os.path.join(


        addon_data_dir,


        "managed_steam_started_{}.json".format(launch_id)


    )





    try:


        with open(path, "r", encoding="utf-8-sig") as handle:


            payload = json.load(handle)


    except (OSError, ValueError, UnicodeError):


        return None





    if not _validate_managed_steam_started(


        payload, launch_id, rom_id


    ):


        return None





    return payload








def _commit_managed_launch_statistics(launch_id, rom_id):

    """Commit verified managed launch statistics exactly once."""

    from resources.lib.commands.view_rendering_commands import cmd_render_vcollection



    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)



    with uow:



        try:



            # Acquire the SQLite write lock before checking or creating the table.



            uow.execute("BEGIN IMMEDIATE")







            uow.execute("""



                CREATE TABLE IF NOT EXISTS managed_launches (



                    launch_id TEXT PRIMARY KEY,



                    rom_id TEXT NOT NULL,



                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP



                )



            """)







            existing = uow.execute(



                "SELECT rom_id FROM managed_launches WHERE launch_id = ?",



                launch_id



            ).fetchone()







            if existing is not None and existing['rom_id'] != rom_id:



                raise ValueError(



                    'Managed launch ID belongs to another ROM: {}'.format(launch_id)



                )







            if existing is None:



                repository = ROMsRepository(uow)



                rom = repository.find_rom(rom_id)



                if rom is None:



                    raise ValueError('Managed launch ROM not found: {}'.format(rom_id))







                uow.execute(



                    "INSERT INTO managed_launches (launch_id, rom_id) VALUES (?, ?)",



                    launch_id, rom_id



                )







                rom.increase_launch_count()



                repository.update_rom(rom)







                logger.info('Managed launch statistics updated for %s', launch_id)



            else:



                logger.info(



                    'Managed launch %s already counted; retrying view rendering',



                    launch_id



                )







            uow.commit()



        except Exception:



            uow.rollback()



            raise







    logger.info('Managed launch statistics committed for ROM %s', rom_id)







    cmd_render_vcollection({



        'vcollection_id': constants.VCOLLECTION_RECENT_ID



    })



    logger.info('Managed launch Recently Played rendering completed')







    cmd_render_vcollection({



        'vcollection_id': constants.VCOLLECTION_MOST_PLAYED_ID



    })



    logger.info('Managed launch Most Played rendering completed')







    _write_managed_launch_ack(launch_id, rom_id)



    logger.info(



        'Managed launch completion acknowledged: launch_id=%s, rom_id=%s',



        launch_id, rom_id



    )







    logger.info('Managed launch bookkeeping completed for ROM %s', rom_id)




@AppMediator.register('MANAGED_STEAM_ROM_WAS_LAUNCHED')
def cmd_process_managed_steam_launch(args):
    """Count a managed Steam launch only after verified game startup."""
    import re
    import xbmcvfs

    if not isinstance(args, dict):
        raise ValueError("Managed Steam launch requires arguments")

    launch_id = args.get("launch_id")
    rom_id = args.get("rom_id")

    if not isinstance(launch_id, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]{1,128}", launch_id
    ):
        raise ValueError("Invalid managed Steam launch ID")

    if not isinstance(rom_id, str) or not rom_id:
        raise ValueError("Invalid managed Steam ROM ID")

    addon_data_dir = xbmcvfs.translatePath(
        "special://profile/addon_data/plugin.program.akl/"
    )

    confirmation = _read_managed_steam_started(
        addon_data_dir, launch_id, rom_id
    )

    if confirmation is None:
        raise RuntimeError(
            "Managed Steam game startup not confirmed: {}".format(
                launch_id
            )
        )

    logger.info(
        "Managed Steam game startup verified: launch_id=%s, app_id=%s",
        launch_id,
        confirmation["steam_app_id"]
    )

    _commit_managed_launch_statistics(launch_id, rom_id)


@AppMediator.register('MANAGED_ROM_WAS_LAUNCHED')



def cmd_process_managed_launch(args):



    """Commit managed launch statistics and render dependent views."""



    from resources.lib.commands.view_rendering_commands import cmd_render_vcollection







    rom_id = args.get('rom_id') if args else None



    if not rom_id:



        raise ValueError('Managed launch requires a ROM ID')







    launch_id = args.get('launch_id') if args else None



    if not isinstance(launch_id, str) or not launch_id.strip():



        raise ValueError('Managed launch requires a unique launch ID')







    logger.info(



        'Managed launch bookkeeping started: launch_id=%s, rom_id=%s',



        launch_id, rom_id



    )







    # Do not count a managed launch until the helper confirms




    # that Windows successfully created the emulator process.




    # The launcher prepares its configuration asynchronously. Resolve the
    # launch type before waiting for an emulator startup confirmation.
    # Steam starts only after Kodi exits and uses post-restart bookkeeping.
    import time

    service_monitor = args.get('_service_monitor')
    launch_type = None
    deadline = time.monotonic() + 2.0

    while True:
        launch_type = _read_managed_launch_type(launch_id, rom_id)

        if launch_type is not None:
            break

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break

        interval = min(0.05, remaining)

        if service_monitor is not None:
            if service_monitor.waitForAbort(interval):
                logger.info(
                    'Managed launch classification interrupted by shutdown: %s',
                    launch_id
                )
                return
        else:
            time.sleep(interval)

    if launch_type == 'steam':
        logger.info(
            'Managed Steam shortcut deferred to post-restart bookkeeping: '
            'launch_id=%s, rom_id=%s',
            launch_id, rom_id
        )
        return

    if launch_type is None:
        logger.warning(
            'Managed launch configuration unavailable or invalid: '
            'launch_id=%s, rom_id=%s',
            launch_id, rom_id
        )
        return

    if not _wait_for_managed_emulator_started(




        launch_id, rom_id, timeout=15, monitor=args.get('_service_monitor')




    ):




        raise RuntimeError(




            "Managed emulator startup not confirmed: {}".format(




                launch_id




            )




        )









    logger.info(




        "Managed emulator startup verified: launch_id=%s",




        launch_id




    )









    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)



    with uow:



        try:



            # Acquire the SQLite write lock before checking or creating the table.



            uow.execute("BEGIN IMMEDIATE")







            uow.execute("""



                CREATE TABLE IF NOT EXISTS managed_launches (



                    launch_id TEXT PRIMARY KEY,



                    rom_id TEXT NOT NULL,



                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP



                )



            """)







            existing = uow.execute(



                "SELECT rom_id FROM managed_launches WHERE launch_id = ?",



                launch_id



            ).fetchone()







            if existing is not None and existing['rom_id'] != rom_id:



                raise ValueError(



                    'Managed launch ID belongs to another ROM: {}'.format(launch_id)



                )







            if existing is None:



                repository = ROMsRepository(uow)



                rom = repository.find_rom(rom_id)



                if rom is None:



                    raise ValueError('Managed launch ROM not found: {}'.format(rom_id))







                uow.execute(



                    "INSERT INTO managed_launches (launch_id, rom_id) VALUES (?, ?)",



                    launch_id, rom_id



                )







                rom.increase_launch_count()



                repository.update_rom(rom)







                logger.info('Managed launch statistics updated for %s', launch_id)



            else:



                logger.info(



                    'Managed launch %s already counted; retrying view rendering',



                    launch_id



                )







            uow.commit()



        except Exception:



            uow.rollback()



            raise







    logger.info('Managed launch statistics committed for ROM %s', rom_id)







    cmd_render_vcollection({



        'vcollection_id': constants.VCOLLECTION_RECENT_ID



    })



    logger.info('Managed launch Recently Played rendering completed')







    cmd_render_vcollection({



        'vcollection_id': constants.VCOLLECTION_MOST_PLAYED_ID



    })



    logger.info('Managed launch Most Played rendering completed')







    _write_managed_launch_ack(launch_id, rom_id)



    logger.info(



        'Managed launch completion acknowledged: launch_id=%s, rom_id=%s',



        launch_id, rom_id



    )







    logger.info('Managed launch bookkeeping completed for ROM %s', rom_id)







@AppMediator.register('ADD_ROM_TO_FAVOURITES')




def cmd_add_rom_to_favourites(args):




    rom_id: str = args['rom_id'] if 'rom_id' in args else None




    if rom_id is None:




        logger.warning('No rom id supplied.')




        kodi.notify_warn(kodi.translate(40951))




        return









    uow = UnitOfWork(globals.g_PATHS.DATABASE_FILE_PATH)




    with uow:




        repository = ROMsRepository(uow)




        rom = repository.find_rom(rom_id)




        rom.add_to_favourites()




        repository.update_rom(rom)




        uow.commit()









    logger.debug(f'Added ROM {rom.get_rom_identifier()} to favourites')




    AppMediator.async_cmd('RENDER_VCOLLECTION_VIEW', {'vcollection_id': constants.VCOLLECTION_FAVOURITES_ID})
