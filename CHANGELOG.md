# Changelog

## v1.0.2 (06-05-2026)
- Added optional Tor anonymization support with session install and cleanup.
- Added runtime dependency bootstrapping for `requests[socks]`, `beautifulsoup4`, and `pywin32` on Windows.
- Added safer request headers, randomized request delays, and retry/backoff support to reduce detection risk.
- Added an optional non-Tor fallback path when Tor is declined.

## v1.0.1 (06-05-2026)
- Fixed support for current LiveJournal post HTML structure.
- Added compatibility for newer LiveJournal date formats.
- Added fallback handling for multiple LiveJournal page layout variants (newer and older markup patterns).

## v1.0.0 (10-31-2023)
- Initial release.
- Archiving LiveJournal posts into markdown files.
- Setting the creation and modification dates for markdown files.
