# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [Unreleased]
### Added
### Changed
* Minor updates to pyproject.toml.
### Deprecated
### Removed
### Fixed
### Security


## [0.4.0] - 2021-08-05
Version increased to avoid conflicts with old packages on PyPI. 


## [0.3.0] - 2021-08-05
### Added
* Package uploaded to PyPI. Thanks to [Adrian Freund](mailto:mail@freundtech.com) for transferring the deepl package
  name.
* Clarify minimum version of requests module to 2.18.


## [0.2.0] - 2021-07-28
### Changed
* Improve exception hierarchy.
* Translator() server_url argument works with and without trailing slash.
* Translator.translate_text() accepts a single text argument, which may be a list or other iterable.
### Fixed
* Fix examples in readme to match function interface changes.


## [0.1.0] - 2021-07-26
Initial version.

[Unreleased]: https://github.com/DeepLcom/deepl-python/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/DeepLcom/deepl-python/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/DeepLcom/deepl-python/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/DeepLcom/deepl-python/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/DeepLcom/deepl-python/releases/tag/v0.1.0
