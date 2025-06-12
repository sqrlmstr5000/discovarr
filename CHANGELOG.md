# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.8]() - 2025-06-12
### Fixed
- media_id in migration_009

## [0.0.7]() - 2025-06-12
### Added
- Trakt integration (watch history only)
- Image caching service using /cache directory
- Added watch_history template variable to Search
- Integration tests for Library and LLM Providers. Some basic unit testing
- Settings page enhancements
- Allow changing PUID/PGUI in container

### Changed
- Using LibraryProviderBase and LLMProviderBase to standardize providers. Refactored providers.
- Added Default User Setting to Library providers. Removed this from the Search page.
- Plex Provider enhancements
- sync_watch_history will sync all history on first attempt, settings.recent_limit after

### Fixed 
- ai_arr replacements, Closes PR #9

## [0.0.6]() - 2025-06-09
### Fixed
- entrypoint.sh issue when VITE_DISCOVARR_URL is missing to properly display error message

## [0.0.5]() - 2025-06-09
### Changed
- Modified the Dockerfile to support defining a PUID/PGID at runtime and setup /config permissions accordingly

## [0.0.4]() - 2025-06-09
### Changed
- Renamed app to discovarr
- Add setting for root_dir_path; Fixes #5
- Moved gemini.limit setting to app.suggestion_limit

## [0.0.3]() - 2025-06-03
### Added
- Ollama support

## [0.0.1]() - 2025-06-01
### Added
- Initlal beta release