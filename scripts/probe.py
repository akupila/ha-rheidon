#!/usr/bin/env python3
"""Dump what the Rheidon+ cloud API returns for your account.

Uses only the standard library, so it runs without Home Assistant:

    RHEIDON_EMAIL=you@example.com RHEIDON_PASSWORD=... python3 scripts/probe.py
    RHEIDON_EMAIL=... RHEIDON_PASSWORD=... python3 scripts/probe.py --watch 10
    RHEIDON_EMAIL=... RHEIDON_PASSWORD=... python3 scripts/probe.py --save-fixture tests/fixtures

The token is redacted from the output, so it is safe to share. --save-fixture
writes one test fixture per charger with ids, serial, location and IP replaced.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import pathlib
import sys
import time
import urllib.parse
import urllib.request

BASE_URL = os.environ.get("RHEIDON_BASE_URL", "http://8.211.24.170:7074")
WATCH_FIELDS = [
    "status",
    "online",
    "power",
    "powerP2",
    "powerP3",
    "electricity",
    "electricityP2",
    "electricityP3",
    "voltage",
    "voltageP2",
    "voltageP3",
    "electricQuantity",
]


def request(method, path, token=None, params=None, body=None):
    url = BASE_URL + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"Content-Type": "application/json", "Accept-Language": "en"}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=20) as resp:
        envelope = json.load(resp)
    if str(envelope.get("code")) not in ("200", "20001") and envelope.get("success") is not True:
        raise ApiError(f"{path} failed: {envelope}")
    return envelope.get("data")


class ApiError(Exception):
    pass


def login(email, password):
    def attempt(pw):
        return request(
            "POST",
            "/app-api/user/login",
            body={"loginType": "PHONE_EMAIL", "userName": email, "password": pw},
        )

    try:
        return attempt(password)
    except ApiError:
        # The iOS app truncates passwords to 16 characters.
        if len(password) <= 16:
            raise
        print("login failed, retrying with the password truncated to 16 characters", file=sys.stderr)
        return attempt(password[:16])


def redact(value):
    if isinstance(value, dict):
        return {k: "<redacted>" if k.lower() in ("token", "password") else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def dump(title, value):
    print(f"===== {title}")
    print(json.dumps(redact(value), indent=2, ensure_ascii=False))


# Fields that identify an account or charger, replaced in saved fixtures.
ID_FIELDS = {"id", "devId", "deviceNo", "userId", "parentAc550Id"}
REPLACED_FIELDS = {
    "devName": "Charger",
    "address": None,
    "province": None,
    "city": None,
    "area": None,
    "remark": None,
    "longitude": None,
    "latitude": None,
    "gpsLongitude": None,
    "gpsLatitude": None,
    "ipaddress": "192.0.2.10",
    "timeZone": "UTC",
}


def save_fixtures(directory, items):
    """Write {"list": ..., "detail": ...} per charger, with identifying values replaced."""
    fake_ids = {}
    counter = itertools.count(1)

    def anonymize(data):
        out = {}
        for key, value in data.items():
            if key in ID_FIELDS and value not in (None, "", "0"):
                if str(value) not in fake_ids:
                    fake_ids[str(value)] = f"{1000000000000000000 + next(counter)}"
                out[key] = fake_ids[str(value)] if key != "deviceNo" else f"TEST{fake_ids[str(value)][-4:]}"
            elif key in REPLACED_FIELDS and value is not None:
                out[key] = REPLACED_FIELDS[key]
            else:
                out[key] = value
        return out

    directory = pathlib.Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for listed, detail in items:
        model = detail.get("deviceModel") or listed.get("deviceModel") or "unknown"
        path = directory / f"{model}.json"
        fixture = {"list": anonymize(listed), "detail": anonymize(detail)}
        path.write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + "\n")
        print(f"===== saved {path}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--watch", type=int, metavar="SECONDS", help="poll device detail at this interval")
    parser.add_argument("--save-fixture", metavar="DIR", help="write an anonymized test fixture per charger to DIR")
    args = parser.parse_args()

    try:
        data = login(os.environ["RHEIDON_EMAIL"], os.environ["RHEIDON_PASSWORD"])
    except ApiError as err:
        sys.exit(str(err))
    token = data["token"]
    dump("login", data)

    devices = request("GET", "/app-api/rt/rt-device-bind-user/list", token)
    dump("rt-device-bind-user/list", devices)

    listed = [d for d in devices or [] if d.get("devId") is not None]
    dev_ids = [d["devId"] for d in listed]
    details = []
    for dev_id in dev_ids:
        detail = request("GET", "/app-api/rt/rt-device-bind-user/detail", token, {"devId": dev_id})
        dump(f"rt-device-bind-user/detail devId={dev_id}", detail)
        details.append(detail)

    if args.save_fixture:
        save_fixtures(args.save_fixture, zip(listed, details))

    if not args.watch:
        return
    print(f"===== polling every {args.watch}s (Ctrl-C to stop)")
    while True:
        for dev_id in dev_ids:
            detail = request("GET", "/app-api/rt/rt-device-bind-user/detail", token, {"devId": dev_id})
            fields = " ".join(f"{k}={detail.get(k)}" for k in WATCH_FIELDS)
            print(f"{time.strftime('%H:%M:%S')} devId={dev_id} {fields}", flush=True)
        time.sleep(args.watch)


if __name__ == "__main__":
    main()
