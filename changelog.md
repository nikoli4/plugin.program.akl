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