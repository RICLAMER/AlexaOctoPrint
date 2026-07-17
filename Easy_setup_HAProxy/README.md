# Easy HAProxy Setup

Alexa local discovery requires the smart-device description and control routes
on TCP port 80. This helper inspects the current listener before making changes.
It never kills the process using port 80.

The helper:

- keeps existing OctoPrint, webcam, HTTPS, and custom HAProxy routes;
- adds only the restricted Alexa OctoPrint root routes;
- refuses to replace Nginx, Caddy, OctoPrint, or another process on port 80;
- validates the complete HAProxy configuration before restart;
- stores a private backup and state file for verified rollback;
- restores the exact backup when the managed configuration has not been edited;
- preserves later HAProxy edits when removing only the managed blocks.

## From the OctoPrint Web Panel

The status button works without system changes. Installing or removing proxy
routes requires root permission. Enable the restricted web helper once through
SSH:

```bash
sudo /home/pi/oprint/bin/python3 \
  -m octoprint_alexaoctoprint.haproxy_setup enable-web \
  --service-user pi \
  --yes
```

If your OctoPrint virtual environment or service user is different, provide
the matching Python path and user:

```bash
sudo /path/to/octoprint/venv/bin/python3 \
  -m octoprint_alexaoctoprint.haproxy_setup enable-web \
  --service-user octoprint \
  --python-executable /path/to/octoprint/venv/bin/python3 \
  --yes
```

Then open `Settings > Alexa OctoPrint > Port 80 routing`:

1. Select **Inspect**.
2. Review the detected listener and route status.
3. Select **Install / update routes** and confirm.
4. Select **Inspect** again and confirm the `ready` status.

The sudo rule permits only `status`, `install`, and `remove` through the
root-owned helper. Remove this permission through SSH with:

```bash
sudo /home/pi/oprint/bin/python3 \
  -m octoprint_alexaoctoprint.haproxy_setup disable-web \
  --yes
```

## From SSH

Download the repository release or clone the repository:

```bash
git clone https://github.com/RICLAMER/AlexaOctoPrint.git
cd AlexaOctoPrint
```

Start the interactive setup:

```bash
sudo python3 Easy_setup_HAProxy/easy_setup_haproxy.py
```

Non-interactive commands are also available:

```bash
sudo python3 Easy_setup_HAProxy/easy_setup_haproxy.py status
sudo python3 Easy_setup_HAProxy/easy_setup_haproxy.py install
sudo python3 Easy_setup_HAProxy/easy_setup_haproxy.py remove
```

Use `--octoprint-port 5000` only when automatic OctoPrint port detection is
incorrect.

## Port 80 Outcomes

- **HAProxy with working managed routes:** no change is needed.
- **HAProxy without the routes:** the helper can merge and validate them.
- **Port 80 free:** the helper can install HAProxy and route to OctoPrint's
  internal port.
- **Another proxy with working routes:** HAProxy is not installed.
- **Another process without working routes:** setup stops without changing or
  terminating that process.
- **OctoPrint directly on port 80:** move OctoPrint to an internal port such as
  5000, then run setup again.

Backups and rollback metadata are stored under:

```text
/var/lib/alexaoctoprint-haproxy/
```
