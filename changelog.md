## 1.7.10

- Fixed a missing Kodi API import that prevented RetroPlayer launches when cache management was initialized.

## 1.7.9

- Improved Kodi RetroPlayer support for compatible ROM archives.
- Added preparation and extraction of supported archived ROMs before launching RetroPlayer.
- Added RetroPlayer cache inspection and cleanup safeguards.
- Protected active playback cache directories and rejected unsafe cache paths.
- Improved optional component descriptions in the AKL setup interface.

## 1.7.8

- Improved Managed Windows Launcher integration for Steam and RetroArch.
- Fixed managed Steam launch handling and launch-statistics integration.
- Improved managed launch tracking and recovery behavior.
- Updated release metadata for Advanced Kodi Launcher: Revival.

## 1.7.7

- Updated the add-on display name to Advanced Kodi Launcher: Revival.
- Improved consistency of Revival branding in Kodi's add-on information.

## 1.7.6

- Added Managed Windows Launcher integration for supported emulators and Steam games.
- Added verified managed launch tracking to improve play counts and Recently Played and Most Played updates.
- Added recovery of pending managed Steam launch statistics when Kodi restarts.
- Added automatic restoration of the last-viewed AKL collection after exiting a game and reopening Kodi.
- Redesigned the Setup Assistant with component, launcher, scraper, and optional skin selection.
- Added Review Component Setup to the Add menu so component settings can be revisited without resetting initial setup.
- Added version-aware Setup Assistant invitations for existing installations, with options to review, postpone, or dismiss.
- Improved setup and configuration of optional launcher and scraper integrations.
- Applied configured default emulator and ROM directories when manually creating launchers and sources.
- Improved default artwork directory handling, including automatic source-specific artwork folders.
- Preserved manually selected artwork directories when no default artwork root is configured.
- Preserved existing ROM source paths when editing sources.
- Improved source setup and removed temporary diagnostic logging.

## 1.7.5

- Added automatic restoration of the last-viewed AKL collection when Kodi restarts after launching a game.
- Applied the configured default emulator directory when manually creating launchers.
- Applied the configured default ROM directory when manually creating sources.
- Improved default artwork directory handling for manually created sources.
- Automatically created source-specific artwork folders when a default artwork root is configured.
- Preserved manually selected artwork directories when no default artwork root is configured.
- Preserved existing ROM source paths when editing sources.
- Improved source setup and removed temporary diagnostic logging.

## 1.7.4

- Fixed scraper callbacks being blocked by a confirmation dialog after saving scraped ROM metadata.
- Removed the obsolete Offline Database scraper from the first-run Setup Wizard.
- Fixed AKL content properties for categories, ROM collections, and launchers so Kodi skins receive the expected values.

## 1.7.3

- Updated the AKL shared module dependency to version 1.4.1.
- Added Console artwork support for system collections.
- Separated system artwork capabilities from game artwork capabilities.
- Improved manual and bulk system scraping to use supported system artwork types.
- Simplified the system scraping interface by removing game-specific scraping options.
- Improved system artwork destination handling.
- Renamed the context menu action to Bulk System Scraper.

## 1.7.2

- Fixed importing local system artwork into the configured default artwork directory.
- Fixed manual artwork imports failing when the destination artwork directory does not yet exist.
- Fixed system artwork not updating immediately after manually replacing an image.
- Improved live artwork refresh handling for both systems and individual games.
- Improved artwork display caching so replaced images refresh without restarting Kodi.

## 1.7.1

- Updated AKL screenshots to showcase the current Arctic: Zephyr - Reloaded (AKL Edition) interface.
- Replaced the older 720p screenshots with three selected current 1080p screenshots.
- Renamed screenshot assets so Kodi refreshes cached add-on screenshots.

## 1.7.0

- Updated the Advanced Kodi Launcher Library Module dependency to version 1.4.0.
- Added Update ROM Collection to scan all collection sources and import newly discovered games.
- Added bulk system scraping with multi-select support.
- Added system scraping support for collections with multiple sources sharing the same artwork directory.
- Added Random Game actions for the full game library and individual collections.
- Added options to hide Sources and Launchers from the AKL root menu.
- Improved root menu organization and customization.
- Added a warning explaining how to restore access to AKL settings when Utilities is hidden.
- Improved default artwork directory handling when creating new systems.
- Improved first-run guidance for the default artwork directory.
- Added additional artwork properties for improved AKL skin integration, including standard thumb artwork and collection controller artwork.
- Improved ROM collection update, scraping, and view refresh behavior.
- Cleaned up redundant and obsolete context-menu actions.
- Improved labels, prompts, warnings, and general interface text.

## 1.6.5

- Updated the AKL module dependency to version 1.3.1.
- Updated the development dependency to script.module.akl 1.3.1.
- Maintenance release; no functional code changes.

## 1.6.4

- Improved the first-run setup wizard and system setup workflow.
- Added support for rescraping an entire system after setup.
- Added a Scrape System management action.
- Added an optional prompt to install the Arctic: Zephyr - Reloaded (AKL Edition) skin after first-run setup.
- Improved first-run skin guidance and setup flow.

## 1.6.3

- Updated Advanced Kodi Launcher Revival icon and fanart assets.
- Changed the add-on metadata to use uniquely named Revival artwork files.
- Using unique artwork paths prevents Kodi's cached legacy AKL artwork from overriding the new Revival branding after an upgrade.

## 1.6.2

- Fixed Recently Played and Most Played artwork loading so all assets are returned for the selected ROMs.
- Added persistent per-platform artwork preferences for AKL-aware skins.
- Added immediate refresh of Recently Played and Most Played virtual collections after artwork preference changes.
- Added Home widget reload support after artwork preference changes.
- Exposed ROM last-played timestamps through Kodi's standard LastPlayed metadata.
- Fixed launching standalone sources.
- Several fixes by mallexxx.
- Moved default asset paths to edit assets/artwork menu.

## Previous

- Separated launchers.
- Implemented sources.
- Search term mode applicable for multi ROM scraping.
- Refactoring of default asset mapping.
- Collections now use import rules from sources.