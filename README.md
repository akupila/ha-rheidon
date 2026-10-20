# Rheidon+ for Home Assistant

An unofficial Home Assistant integration for Rheidon+ EV chargers. It reads
your charger's power, energy and status from the Rheidon cloud (the same
service the Rheidon+ app uses), and it can start and stop charging.

It has been tested with a **WB500-11K-C-EU** connected over Wi-Fi. Other Rheidon
chargers that appear in the Rheidon+ app over Wi-Fi will probably work too.
If you try one, please open an issue to say how it went.

> This project isn't affiliated with or endorsed by Rheidon. It uses an
> undocumented API that could change at any time.

## Requirements

- Home Assistant 2024.11 or newer. The integration's logo needs 2026.3 or newer;
  older versions show a placeholder.
- A Rheidon+ account (email and password) with the charger added in the
  Rheidon+ app over Wi-Fi. Chargers paired only over Bluetooth don't appear in
  the cloud and aren't supported.

## Installation

### HACS (recommended)

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=akupila&repository=ha-rheidon&category=integration)

Or add it by hand:

1. In Home Assistant, open **HACS**, then use the ⋮ menu (top right) to open
   **Custom repositories**.
2. Enter `https://github.com/akupila/ha-rheidon`, choose the type **Integration**,
   and click **Add**.
3. Search HACS for **Rheidon+**, open it and click **Download**.
4. Restart Home Assistant.

### Manual

1. Download this repository, for example as a ZIP from the green **Code** button.
2. Copy `custom_components/rheidon` into your Home Assistant configuration
   directory, so that you have `config/custom_components/rheidon/manifest.json`.
3. Restart Home Assistant.

## Configuration

[![Open your Home Assistant instance and start setting up Rheidon+.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=rheidon)

1. Go to **Settings → Devices & services → Add integration** and search for
   **Rheidon+**.
2. Sign in with the email and password you use in the Rheidon+ app.
3. Leave **API URL** at its default.

Each charger on your account appears as a device.

## Entities

| Entity | Type | Notes |
|---|---|---|
| Power | sensor (kW) | total across all phases |
| Power, Current, Voltage L1–L3 | sensors | L2 and L3 only on three-phase chargers |
| Session energy | sensor (kWh) | energy delivered since the car was plugged in |
| Status | sensor | plugged in, charging, unplugged, fault, emergency stop, paused |
| Charge start, Charge end | sensors (timestamp) | start and end of the current or last charge |
| Charging | binary sensor | |
| Online | binary sensor (diagnostic) | whether the charger is connected to the Rheidon cloud |
| Charge | switch | starts and stops charging |
| Charge current limit | number | 6 A up to the charger's maximum |
| Charging mode | select | Plug and charge, ECO, MAX, Manual |

The integration polls the cloud every 30 seconds. While the car charges, the
charger sends new readings about every 2 minutes, so the values update at that
rate.

## Energy dashboard

To track how much energy the charger uses:

1. Go to **Settings → Dashboards → Energy**.
2. Under **Individual electrical devices**, click **Add device**.
3. For **Device energy consumption**, choose **Session energy**.
4. For **Device power consumption**, choose **Power**.

Session energy starts again from zero each time the car is plugged in. Home
Assistant treats that drop as a meter reset, so the daily and monthly totals
stay correct.

## Things to know

- **Your password is sent unencrypted.** The Rheidon cloud API only works over
  plain HTTP, so your password and session token cross the internet
  unencrypted, exactly as they do from the Rheidon+ app. Use a password you
  don't use anywhere else.
- **Long passwords are cut to 16 characters.** The Rheidon+ iOS app silently
  cuts passwords off at 16 characters when you register. If your password is
  longer, enter it in full anyway; the integration retries with the first 16
  characters.
- **Commands go through the cloud.** Start, stop, current and mode changes
  need the Rheidon cloud and the charger to be online.

## Troubleshooting

On the integration's page, open the ⋮ menu and choose **Enable debug logging**.
Reproduce the problem, then disable debug logging, which downloads the log.
When you open an issue, attach that log. It doesn't contain your password or
token, but check it for anything else you'd rather not share.

## Development

- [FLOW.md](FLOW.md) documents the API: endpoints, fields, status codes, and
  what has and hasn't been verified.
- [AGENTS.md](AGENTS.md) is a guide for working on this repository, and is
  also read by AI coding assistants.
- `scripts/probe.py` uses only the Python standard library. It prints the raw
  API responses for your account, with the token removed:

  ```sh
  RHEIDON_EMAIL=you@example.com RHEIDON_PASSWORD=... python3 scripts/probe.py
  RHEIDON_EMAIL=you@example.com RHEIDON_PASSWORD=... python3 scripts/probe.py --watch 30
  ```

- `make test` runs the tests. They need Python 3.14; set `PYTHON` if it isn't
  on your path as `python3.14`. CI runs the same tests, plus Home Assistant's
  `hassfest` and HACS validation, on every pull request.
- `make check` checks the Python syntax. With SSH access to Home Assistant,
  for example through the Terminal & SSH add-on, `make install` copies the
  integration across and `make restart` restarts Home Assistant. If your
  instance isn't at `root@homeassistant.local`, set `HA_HOST`.

## Adding another Rheidon charger

The tests run once for each charger in `tests/fixtures/`. To add yours:

1. Capture a fixture. It strips ids, the serial number, location and IP
   address, but check the file before committing it:

   ```sh
   RHEIDON_EMAIL=you@example.com RHEIDON_PASSWORD=... \
     python3 scripts/probe.py --save-fixture tests/fixtures
   ```

   This writes `tests/fixtures/<model>.json`. Capturing it while the car is
   charging makes the test more useful.
2. Run `make test`. If something fails, it shows what your charger reports
   differently. Fix the integration, not the fixture.
3. Open a pull request with the fixture, any code changes, and what you
   checked in Home Assistant.

## License

[MIT](LICENSE). "Rheidon" and the Rheidon logos belong to their owner and are
included only to identify the product in Home Assistant.
