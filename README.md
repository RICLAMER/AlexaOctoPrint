# Alexa OctoPrint

Alexa OctoPrint is an OctoPrint plugin that simulates local smart devices for
selected printer actions. It does not require an Alexa skill, an account on an
external integration platform, or a cloud backend.

Install the plugin, enable the actions you want, and ask:

> Alexa, search for new devices.

Discovery and control traffic stay on the local network.

## Status

This project is an alpha release. Test every enabled action from the OctoPrint
settings page before using it by voice.

## Requirements

- OctoPrint 1.6.0 or newer
- Python 3.7 or newer
- A genuine Echo device on the same LAN as OctoPrint
- TCP port 80 routing for the local smart-device endpoints
- Optional: OctoPrint-Enclosure for printer power and light outputs

## Install

### Plugin Manager

Open `Settings > Plugin Manager`, select `Install from URL`, and use the release
archive:

```text
https://github.com/RICLAMER/AlexaOctoPrint/releases/latest/download/OctoPrint-AlexaOctoPrint.zip
```

The latest tested upload package is also kept at
[`plugin/OctoPrint-AlexaOctoPrint.zip`](plugin/OctoPrint-AlexaOctoPrint.zip).

Restart OctoPrint after installation.

### Command Line

```bash
~/oprint/bin/pip install \
  https://github.com/RICLAMER/AlexaOctoPrint/releases/latest/download/OctoPrint-AlexaOctoPrint.zip
sudo service octoprint restart
```

## Port 80

Alexa local discovery expects the smart-device description and control routes
at the root of TCP port 80. HAProxy is **not mandatory** when another existing
reverse proxy already exposes the required routes correctly.

Common cases:

- Existing HAProxy with Alexa OctoPrint routes: no additional proxy is needed.
- Existing Nginx, Caddy, or another proxy with equivalent routes: keep it.
- Port 80 free while OctoPrint uses an internal port: a port 80 proxy is still
  required; the Easy Setup can install HAProxy.
- OctoPrint directly using port 80: move OctoPrint to an internal port such as
  5000 before placing a reverse proxy on port 80.
- Another process using port 80: the Easy Setup reports it and makes no change.

The managed rules accept only:

- `GET /description.xml`
- `POST /api`
- `GET /api/<40-hex-character-installation-key>`
- the matching `/lights` read and state routes

Normal OctoPrint endpoints such as `/api/job` and `/api/files` never match these
rules.

### Easy Setup

The helper is documented in
[`Easy_setup_HAProxy/README.md`](Easy_setup_HAProxy/README.md). It can:

- inspect the current port 80 listener;
- preserve existing HAProxy routes;
- replace legacy Alexa OctoPrint rules;
- validate the full configuration before restart;
- save rollback state under `/var/lib/alexaoctoprint-haproxy/`;
- restore the exact saved configuration when it is safe to do so.

For interactive SSH setup:

```bash
git clone https://github.com/RICLAMER/AlexaOctoPrint.git
cd AlexaOctoPrint
sudo python3 Easy_setup_HAProxy/easy_setup_haproxy.py
```

The settings page also provides **Inspect**, **Install / update routes**, and
**Restore previous configuration** controls. Systems that require a sudo
password need the one-time, restricted web helper described in the Easy Setup
guide.

## Configure and Discover

1. Open `Settings > Alexa OctoPrint`.
2. Select Portuguese, English, or Spanish.
3. Enable only the actions you intend to use.
4. Configure temperatures, movement, G-code, files, and Enclosure Labels.
5. Test actions with the **Run**, **On**, and **Off** buttons.
6. Select **Refresh** and confirm that SSDP is running.
7. Ask Alexa to search for new devices.

The action list changes immediately when a different language is selected.
Save the settings before Alexa discovery. Alexa may retain names from devices
that were already discovered, so remove those devices before discovering them
again in another language.

When upgrading from 0.1.x, remove the old `Octo ...` devices from Alexa before
discovery. Version 0.2.0 replaces the shared legacy username with a unique
installation username and uses the new device names below.

## Voice Commands

Each table shows the default action names and voice examples for the selected
plugin language. Custom device names remain available in settings and are not
translated automatically.

### Portuguese

| Action | Voice command |
| --- | --- |
| Impressora 3D | "Alexa, ligar impressora 3D" / "Alexa, desligar impressora 3D" |
| Luz da Impressora | "Alexa, ligar luz da impressora" / "Alexa, desligar luz da impressora" |
| Pausar Impressão | "Alexa, pausar impressão" |
| Retomar Impressão | "Alexa, retomar impressão" |
| Cancelar Impressão | "Alexa, cancelar impressão" |
| Levar Impressora para Home | "Alexa, levar impressora para Home" |
| Nivelar Mesa | "Alexa, nivelar mesa" |
| Subir Eixo Z | "Alexa, subir eixo Z" |
| Baixar Eixo Z | "Alexa, baixar eixo Z" |
| Extrudar Filamento | "Alexa, extrudar filamento" |
| Recolher Filamento | "Alexa, recolher filamento" |
| Aquecer Mesa | "Alexa, aquecer mesa" / "Alexa, ligar aquecimento da mesa" |
| Desligar Mesa | "Alexa, desligar mesa" / "Alexa, desligar aquecimento da mesa" |
| Aquecer Bico para PLA | "Alexa, aquecer bico para PLA" |
| Aquecer Bico para ABS | "Alexa, aquecer bico para ABS" |
| Aquecer Bico para PETG | "Alexa, aquecer bico para PETG" |
| Desligar Aquecimento do Bico | "Alexa, desligar aquecimento do bico" / "Alexa, desligar bico" |
| Motores da Impressora | "Alexa, ligar motores da impressora" / "Alexa, desligar motores da impressora" |
| Imprimir Último Arquivo | "Alexa, imprimir último arquivo" |
| Imprimir Peça Um | "Alexa, imprimir peça um" |
| Imprimir Peça Dois | "Alexa, imprimir peça dois" |
| Imprimir Peça Três | "Alexa, imprimir peça três" |
| Emergência da Impressora | "Alexa, emergência da impressora" / "Alexa, parar impressora imediatamente" |

### English

| Action | Voice command |
| --- | --- |
| 3D Printer | "Alexa, turn on 3D printer" / "Alexa, turn off 3D printer" |
| Printer Light | "Alexa, turn on printer light" / "Alexa, turn off printer light" |
| Pause Print | "Alexa, pause print" |
| Resume Print | "Alexa, resume print" |
| Cancel Print | "Alexa, cancel print" |
| Home Printer | "Alexa, home printer" |
| Level Bed | "Alexa, level bed" |
| Raise Z Axis | "Alexa, raise Z axis" |
| Lower Z Axis | "Alexa, lower Z axis" |
| Extrude Filament | "Alexa, extrude filament" |
| Retract Filament | "Alexa, retract filament" |
| Heat Bed | "Alexa, heat bed" / "Alexa, turn on bed heating" |
| Turn Off Bed | "Alexa, turn off bed" / "Alexa, turn off bed heating" |
| Heat Nozzle for PLA | "Alexa, heat nozzle for PLA" |
| Heat Nozzle for ABS | "Alexa, heat nozzle for ABS" |
| Heat Nozzle for PETG | "Alexa, heat nozzle for PETG" |
| Turn Off Nozzle Heating | "Alexa, turn off nozzle heating" / "Alexa, turn off nozzle" |
| Printer Motors | "Alexa, turn on printer motors" / "Alexa, turn off printer motors" |
| Print Last File | "Alexa, print last file" |
| Print Part One | "Alexa, print part one" |
| Print Part Two | "Alexa, print part two" |
| Print Part Three | "Alexa, print part three" |
| Printer Emergency | "Alexa, printer emergency" / "Alexa, stop printer immediately" |

### Spanish

| Action | Voice command |
| --- | --- |
| Impresora 3D | "Alexa, enciende impresora 3D" / "Alexa, apaga impresora 3D" |
| Luz de la Impresora | "Alexa, enciende luz de la impresora" / "Alexa, apaga luz de la impresora" |
| Pausar Impresión | "Alexa, pausa impresión" |
| Reanudar Impresión | "Alexa, reanuda impresión" |
| Cancelar Impresión | "Alexa, cancela impresión" |
| Llevar Impresora a Inicio | "Alexa, lleva impresora a inicio" |
| Nivelar Cama | "Alexa, nivela cama" |
| Subir Eje Z | "Alexa, sube eje Z" |
| Bajar Eje Z | "Alexa, baja eje Z" |
| Extruir Filamento | "Alexa, extruye filamento" |
| Retraer Filamento | "Alexa, retrae filamento" |
| Calentar Cama | "Alexa, calienta cama" / "Alexa, enciende calentamiento de cama" |
| Apagar Cama | "Alexa, apaga cama" / "Alexa, apaga calentamiento de cama" |
| Calentar Boquilla para PLA | "Alexa, calienta boquilla para PLA" |
| Calentar Boquilla para ABS | "Alexa, calienta boquilla para ABS" |
| Calentar Boquilla para PETG | "Alexa, calienta boquilla para PETG" |
| Apagar Calentamiento de la Boquilla | "Alexa, apaga calentamiento de la boquilla" / "Alexa, apaga boquilla" |
| Motores de la Impresora | "Alexa, enciende motores de la impresora" / "Alexa, apaga motores de la impresora" |
| Imprimir Último Archivo | "Alexa, imprime último archivo" |
| Imprimir Pieza Uno | "Alexa, imprime pieza uno" |
| Imprimir Pieza Dos | "Alexa, imprime pieza dos" |
| Imprimir Pieza Tres | "Alexa, imprime pieza tres" |
| Emergencia de la Impresora | "Alexa, emergencia de la impresora" / "Alexa, detén impresora inmediatamente" |

Alexa language behavior can vary by Echo model and account locale. A custom
device name can be used when a default phrase is not recognized reliably.

## Configurable Parameters

- Bed temperature: 100 C by default
- PLA nozzle temperature: 200 C
- ABS nozzle temperature: 240 C
- PETG nozzle temperature: 235 C
- Z movement: 2 mm at 600 mm/min
- Extrusion: 5 mm at 300 mm/min
- Retraction: 5 mm at 1800 mm/min
- Homing, leveling, motor, shutdown, and emergency G-code
- Three selectable OctoPrint file slots
- Enclosure output Labels for printer power and light

## Enclosure Plugin

Printer power and light actions are optional. When OctoPrint-Enclosure is
loaded, Alexa OctoPrint reads its current output Labels and presents them in
dropdowns. Label matching ignores capitalization and extra whitespace.

If OctoPrint-Enclosure is missing, disabled, or does not contain the selected
Label:

- Alexa OctoPrint continues running;
- unrelated actions remain available;
- the settings page shows the detected condition;
- power or light commands return a controlled error in Debug.

## Safety

- Print Last File, the three file slots, and Printer Emergency are disabled by
  default.
- Cancel Print always requires the command twice within 15 seconds.
- Motion, extrusion, motor, printing, and power actions are blocked while the
  printer is printing or paused unless explicitly allowed.
- Printer power off is blocked while printing by default.
- Momentary actions reset their reported smart-device state automatically.
- Emergency uses `M112`, `M104 S0`, and `M140 S0` by default.

## Debug

The settings page includes:

- SSDP state, discovery counter, and last Echo address;
- description URL and Hue HTTP request counters;
- enabled device IDs and current states;
- Enclosure availability and discovered Labels;
- recent actions and controlled errors;
- manual action execution;
- port 80 routing inspection.

Local diagnostic endpoints:

- `/plugin/alexaoctoprint/description.xml`
- `/plugin/alexaoctoprint/espalexa`
- `/plugin/alexaoctoprint/debug/status`

The per-installation smart-device username is never displayed or written to
Debug logs; only a short suffix is shown for diagnostics.

## Updates

Alexa OctoPrint uses OctoPrint's
`octoprint.plugin.softwareupdate.check_config` hook with the
`github_release` check type. Releases are tagged with the plugin version, and
OctoPrint installs the matching GitHub tag archive:

```text
https://github.com/RICLAMER/AlexaOctoPrint/archive/{target_version}.zip
```

Every stable Release also includes an installable asset named exactly
`OctoPrint-AlexaOctoPrint.zip`. The OctoPrint Plugin Repository uses the
permanent `releases/latest/download` URL for that asset.

This follows the release and update pattern used by
[OctoPrint-BLTouch](https://github.com/jneilliii/OctoPrint-BLTouch).

## Privacy and Security

- No external integration account, skill, telemetry, or cloud relay is used.
- A random 40-character local username is generated for each installation.
- Requests with another username receive a local unauthorized response.
- Reverse-proxy rules validate both HTTP method and exact path shape.
- Normal OctoPrint API traffic is not routed to the plugin.

The local username is an emulated device credential, not an Amazon, Philips, or
OctoPrint account key.

## Acknowledgements

Local discovery behavior was informed by
[Aircoookie/Espalexa](https://github.com/Aircoookie/Espalexa), an MIT-licensed
Arduino library for local Alexa device control. Alexa, Echo, Philips, and Hue
are trademarks of their respective owners. This project is not affiliated with
or endorsed by Amazon or Signify.

## License

Copyright 2026 RICLAMER.

Alexa OctoPrint is free software licensed under the
[GNU Affero General Public License v3.0 or later](LICENSE)
(`AGPL-3.0-or-later`).
