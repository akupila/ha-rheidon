# Agent guide: Rheidon+ Home Assistant integration

This repo contains an unofficial Home Assistant custom integration for Rheidon+ EV
chargers (tested with a WB500-11K-C-EU). It talks to the Rheidon cloud REST API,
which was reverse engineered from the Rheidon+ app. **Read `FLOW.md` before
changing anything that touches the API.** It is the protocol reference, and
it records what has been verified against a real account and what is still assumed.

## Layout

- `custom_components/rheidon/`: the integration.
  - `api.py`: the async API client. It has **no Home Assistant imports**, so it
    can be tested on its own.
  - `coordinator.py`: polls `list` and then `detail` for each `devId` every 30 s.
  - `entity.py`, `sensor.py`, `binary_sensor.py`, `switch.py`, `number.py`, `select.py`: the entities.
  - `strings.json`: the UI text. **`translations/en.json` must be an identical copy**
    (custom integrations load `translations/`). After editing it, run
    `cp custom_components/rheidon/strings.json custom_components/rheidon/translations/en.json`.
  - `icons.json`: entity icons, keyed by `translation_key`.
  - `brand/`: the icon and logo (Home Assistant 2026.3+ reads them from here).
    The icon comes from the app's launcher icon, and the logo from its
    `static/images/rheidontech.png` wordmark. The wordmark is white, so
    `dark_logo*.png` uses it unchanged and `logo*.png` is the same image
    recoloured to #212121.
- `scripts/probe.py`: uses only the standard library. Dumps raw API responses for the
  account in `.envrc`, with the token redacted. `--watch N` polls `detail`.
- `FLOW.md`: the protocol documentation. Keep it up to date when you learn something new.

## How auth works

- **Host:** `http://8.211.24.170:7074`, which is **plain HTTP**. `api.rheidon-tech.com`
  resolves to the same IP, but its HTTPS endpoint is broken. Don't switch the
  default to HTTPS unless you've confirmed it works.
- **Login:** `POST /app-api/user/login` with
  `{"loginType": "PHONE_EMAIL", "userName": email, "password": password}`.
  The password is sent in plaintext, the same way the official apps send it.
  The response contains `data.token` (128 characters).
- **Every other request** sends `Authorization: Bearer <token>`, `Accept-Language: en`
  and `timeutc: UTC±N`.
- **Response envelope:** HTTP 200 with `{code, success, message, data}`. Success is
  code `200` or `20001`, or `success: true`. Codes `A00004`, `A00006`, `A00007`
  and `U0230`, as well as HTTP 401, mean the token expired. In that case the client
  logs in again and retries once. There is no refresh token.
- **16-character passwords:** the iOS app silently cuts passwords off at
  16 characters, so accounts created there only accept the first 16 characters.
  `RheidonClient.login()` tries the full password first. If that fails and the
  password is longer than 16 characters, it retries with the first 16 and keeps
  using that. A wrong password and an unknown account both return
  `S5004`, so the error can't tell you which one it was.
- **Other transports:** the integration deliberately uses only the REST API.
  Don't add other ways of talking to the cloud or charger without asking the
  user first.

## Credentials and safety

- **Where they live:** test credentials are in `.envrc` (`RHEIDON_EMAIL`,
  `RHEIDON_PASSWORD`). It's gitignored. Load it with
  `set -a; source .envrc; set +a`.
- **Never print, echo, log or commit the password, the token or the user's email.**
  Before showing command output, replace those values with placeholders. Inspect
  `.envrc` only for the shape of its values, for example
  `sed -E 's/=.*/=<redacted>/' .envrc`.
- **Limit failed logins.** Every failed login counts against the user's real
  account, and the server's lockout policy is unknown. Don't try guessed password
  variations in a loop. If a login fails, stop and investigate first.
- **Read-only by default.** Calls like `list`, `detail` and `charge-record` are
  safe to make. Commands such as start/stop charging, changing the current or
  changing the mode affect the user's real car charger, so only send them when the
  user explicitly asks.
- **Traffic captures.** HAR files from mitmproxy contain the password and token
  in cleartext. Never read them directly into the conversation. Parse them with
  a script that masks those values first, and keep the files out of the repo.

## Data gotchas (verified)

- **Units:** `power*` are kW per phase, `electricity*` are A, and `voltage*` are V.
  `electricQuantity` is the kWh delivered since the car was plugged in. It keeps
  counting across pause and resume, and it is the sensor used in the Energy
  dashboard.
- **`list` vs `detail`:** `list` puts the session energy in `electricity` and leaves
  `electricQuantity` null. `detail` gets both right, so `detail` must override `list`.
- **`status` codes:** 1 plugged in, 2 charging, 3 unplugged, 4 fault, 5 emergency
  stop, 6 discharging, 7 paused.
- **Phases:** `phase` (3) decides whether L2/L3 entities exist. The fallback is the
  model name: `7K2`/`3K6` are single-phase.
- **Timestamps:** `chargeStartTime`/`chargeEndTime` are in the charger's
  `timeZone` (an IANA name such as Europe/Berlin). `lastReportTime`, `createTime` and the envelope
  `time` are in server time (UTC+8). The `timeutc` header doesn't change `detail`.
- **Update rate:** `detail` meter values update every 2 minutes while
  charging (verified), so polling faster than 30 s won't help.
- **Large ids:** `devId` and other ids are large numbers sent as strings. Keep them
  as strings.

## Testing

- **Run the tests with `make test`.** It uses `pytest-homeassistant-custom-component`
  (pinned in `requirements_test.txt`), which needs Python 3.14. The system
  Python here is 3.9, so the first run must go through Nix:
  `nix shell nixpkgs#python314 -c make test`. That creates `.venv/`; later runs
  can use plain `make test`. Pass arguments with `PYTEST_ARGS`, e.g.
  `make test PYTEST_ARGS="-k sensor -x"`.
- **CI** (`.github/workflows/ci.yml`) runs pytest, `hassfest` and HACS validation
  on pushes to main and on pull requests.
- **Each file in `tests/fixtures/` is one charger.** The files are captured with
  `scripts/probe.py --save-fixture tests/fixtures`, which replaces ids, serial
  number, location and IP. Device tests in `test_sensor.py` and
  `test_controls.py` run once per file, and they derive their expected values
  from the fixture. A new model therefore needs its fixture, plus code changes
  only where the expectations don't hold. Don't hand-edit fixtures to make
  tests pass.
- **`api.py` tests** use a fake cloud (`FakeCloud` in `tests/test_api.py`), not
  network calls. Extend it when the client learns new endpoints.
- **`make check`** compiles the integration with the system Python 3.9 as a
  quick syntax check. Keep the integration code 3.9-parseable:
  `from __future__ import annotations` is in every module, and avoid `match`
  statements, the `type X = ...` alias syntax and parenthesised context
  managers. Tests only run on 3.14 and don't have that restriction.
- **The user's Home Assistant.** `make install` copies the integration over SSH
  (`HA_HOST`, default `root@homeassistant.local`), and `make restart` restarts
  Home Assistant. Only run these when the user asks, because they change the
  user's live Home Assistant.
- **API changes:** check them against the live API with `scripts/probe.py`
  (read-only), then cover them in `tests/test_api.py`.
- After running Python, delete any `__pycache__/` directories it created.

## Version control

- **The user uses jj (Jujutsu), not raw git.** Use `jj` commands such as
  `jj st`, `jj diff`, `jj commit -m`, `jj squash` and `jj log`.
- **`main` is published at github.com/akupila/ha-rheidon.** jj treats pushed
  changes as immutable, so don't rewrite them. Put new work in a new, focused
  change on top with a clear description, one change per significant piece of
  work.
- **Don't push** (`jj git push`) unless the user asks.
- Follow the user's attribution instructions for commit messages.

## Code style

- Follow current Home Assistant conventions:
  - entity descriptions with `value_fn`
  - `has_entity_name` and `translation_key`
  - `entry.runtime_data` for the coordinator
  - `ConfigEntryAuthFailed`, which starts reauth
- Match the comment density and naming of the surrounding code. Comments should
  explain non-obvious protocol facts and point to where they came from.
- **Keep `api.py` free of Home Assistant imports.** Raise `RheidonAuthError`,
  `RheidonConnectionError` or `RheidonApiError`. The coordinator and entities
  translate those into Home Assistant exceptions.
