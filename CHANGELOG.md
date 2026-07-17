# Changelog

## 0.2.0 - 2026-07-17

- Made the settings action list react immediately to Portuguese, English, and
  Spanish language selection while preserving explicit custom names.
- Translated the documented action-name columns for all three languages.
- Changed the gallery installation URL to the permanent latest stable Release
  asset.
- Published the complete plugin source under `Source/` and changed the license
  to AGPL-3.0-or-later.
- Replaced the custom update manifest with GitHub Releases.
- Generated a unique local Hue username for every installation and rejected
  unknown usernames.
- Restricted HAProxy ACLs by exact path shape and HTTP method.
- Added reversible Easy HAProxy Setup for the web panel and SSH.
- Removed network, SSDP, cancel timing, test-device, and SSDP reload controls
  from the settings page.
- Removed the standalone Teste Alexa development code.
- Replaced the `Octo` command prefix with Portuguese, English, and Spanish
  device names.
- Added bidirectional printer power, printer light, and motor actions.
- Added Enclosure output Label discovery and dropdown selection with controlled
  behavior when OctoPrint-Enclosure is unavailable.
- Matched the successful standalone Alexa state response and connection
  behavior.

## 0.1.7 - 2026-07-16

- Added the official OctoPrint Software Update check hook.
- Added public `version.json` and stable package URLs.
- Added English installation and HAProxy configuration documentation.

## 0.1.6 - 2026-07-16

- Added temporary Hue state confirmation for momentary Alexa actions.
- Fixed OctoPrint-Enclosure integration for `active_low` Power and LIGHT outputs.
- Added physical GPIO state verification before reporting success.

## 0.1.5 - 2026-07-16

- Matched the Espalexa discovery protocol and explicit TCP port 80 URLs.
- Added the Hue username and response flow used by Echo local discovery.
