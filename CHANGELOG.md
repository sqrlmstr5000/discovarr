# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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