# AlexaOctoPrint

AlexaOctoPrint is an OctoPrint plugin that exposes selected printer actions to Alexa on the local network by emulating the parts of SSDP and the Philips Hue API used by local device discovery.

No external cloud backend is required.

## Status

This project is an alpha implementation. Test every action from the OctoPrint settings page before allowing Alexa discovery.

## Requirements

- OctoPrint running on Python 3.7 or newer
- An Echo device on the same LAN as OctoPrint
- A reverse proxy listening on TCP port 80 and forwarding the Hue routes to OctoPrint
- Optional: OctoPrint-Enclosure for printer power and light outputs

## Installation

### Plugin Manager

Open `Settings > Plugin Manager`, select `Install from URL`, and use:

```text
https://raw.githubusercontent.com/RICLAMER/AlexaOctoPrint/main/plugin/OctoPrint-AlexaOctoPrint.zip
```

You can also download [the latest package](plugin/OctoPrint-AlexaOctoPrint.zip) and upload it through the Plugin Manager.

### Command Line

```bash
~/oprint/bin/pip install https://raw.githubusercontent.com/RICLAMER/AlexaOctoPrint/main/plugin/OctoPrint-AlexaOctoPrint.zip
sudo service octoprint restart
```

### Required HAProxy Routing on OctoPi

Alexa local Hue discovery expects TCP port 80 and root paths such as `/description.xml` and `/api/...`. OctoPi already uses HAProxy on port 80, so do not stop HAProxy and do not start another HTTP server on that port.

1. Back up `/etc/haproxy/haproxy.cfg`.
2. Merge the rules from [`plugin/haproxy.cfg.example`](plugin/haproxy.cfg.example) into the existing `frontend public` section and append the `alexaoctoprint_hue` backend.
3. Validate the complete configuration before restarting:

```bash
sudo haproxy -c -f /etc/haproxy/haproxy.cfg
sudo systemctl restart haproxy
sudo systemctl restart octoprint
```

The example is a snippet, not a replacement for the complete system configuration. Other reverse proxies must implement equivalent selective routing while leaving normal OctoPrint traffic unchanged.

## Alexa Discovery

1. Install and restart OctoPrint.
2. Open OctoPrint settings, then `AlexaOctoPrint`.
3. Confirm the advertised host, port, and path.
4. Press `Refresh` and verify that the debug status shows SSDP running.
5. Ask Alexa to discover devices.

The plugin advertises a Hue-compatible bridge and creates one virtual on/off light per enabled action. Actions are momentary commands, so the usual phrase is similar to:

```text
Alexa, turn on Octo Pause
```

The exact phrasing depends on the Alexa language configured in your account/device.

After a successful momentary action, its Hue state remains on briefly so Echo can confirm the command, then resets automatically so the same action can be called again.

## Command Languages

The settings page supports Portuguese, English, and Spanish default device names. Each action also has a custom name field, so you can tune names for your Alexa account.

Default Portuguese commands include:

- Octo Pausar
- Octo Retomar
- Octo Home
- Octo Nivelamento
- Octo Subir Eixo Z
- Octo Descer Eixo Z
- Octo Cancelar
- Octo Ligar Impressora
- Octo Ligar Luz Impressora
- Octo Desligar Impressora
- Octo Imprimir Ultimo Arquivo
- Octo Retract
- Octo Extrude
- Octo Aquecer Mesa
- Octo Desligar Mesa
- Octo Aquecer HotEnd PLA
- Octo Aquecer HotEnd ABS
- Octo Aquecer HotEnd PETG
- Octo Desligar HotEnd
- Octo Desligar Motores
- Octo Emergencia
- Octo Imprimir Peca 1
- Octo Imprimir Peca 2
- Octo Imprimir Peca 3

## Safety Defaults

- `Print last file`, `Emergency`, and the three print slots are disabled by default.
- Cancel can require two calls within a configurable timeout.
- Motion and extrusion actions are blocked while printing unless explicitly allowed.
- Power off through Enclosure is blocked while printing unless explicitly allowed.
- Temperatures, extrusion length, Z movement distance, feedrate, and G-code are editable in settings.

## Enclosure Plugin

The Enclosure integration controls outputs by label. Defaults:

- Printer power: `Power`
- Printer light: `LIGHT`

Label matching ignores capitalization and extra whitespace. AlexaOctoPrint resolves the Enclosure plugin implementation, writes the configured GPIO with `active_low` support, and reads the physical output state back before reporting success. Change the labels in AlexaOctoPrint settings if your Enclosure outputs use different names.

## Debugging

The settings page exposes:

- SSDP running state
- Discovery request counters
- Last Echo address that sent `M-SEARCH`
- Advertised `description.xml` URL
- Enabled Hue device IDs
- Recent action events and errors
- Manual `Run` button for every action

The plugin also exposes local diagnostic endpoints:

- `/plugin/alexaoctoprint/description.xml`
- `/plugin/alexaoctoprint/espalexa`
- `/plugin/alexaoctoprint/debug/status`

## Network Notes

Alexa Echo generations that use local Hue discovery expect the emulated bridge on TCP port 80. Keep the advertised port set to `80`.

OctoPi normally uses HAProxy on port 80 and runs OctoPrint internally on port 5000. These services can coexist: HAProxy keeps ownership of port 80, forwards `/description.xml`, `POST /api`, and the AlexaOctoPrint Hue username paths to `/plugin/alexaoctoprint` on port 5000, and sends all other traffic to the normal OctoPrint backend. Do not start a second HTTP listener on port 80.

The public [`plugin/haproxy.cfg.example`](plugin/haproxy.cfg.example) contains the required selective routes. Back up and validate the system HAProxy configuration before applying those routes.

Some Alexa/Hue discovery behavior is strict about local network multicast. If devices are not found, check:

- Echo and Raspberry Pi are on the same subnet
- Client isolation is disabled on Wi-Fi
- UDP multicast to `239.255.255.250:1900` is not blocked
- The advertised URL opens from another device on the LAN

## Updates

Alexa OctoPrint registers the official `octoprint.plugin.softwareupdate.check_config` hook. OctoPrint reads the latest version from [`plugin/version.json`](plugin/version.json) and installs the current public ZIP through its Software Update plugin.

The version check may be cached by OctoPrint. Use `Settings > Software Update > Advanced options > Force check for update` when validating a newly published version.

## Privacy

The plugin does not require an Alexa skill, external account, cloud backend, telemetry service, or analytics endpoint. Discovery and control traffic stay on the local network. OctoPrint still needs internet access when checking for or downloading updates from GitHub.

## License

Copyright 2026 RICLAMER. Distributed under the proprietary terms in [LICENSE](LICENSE).

