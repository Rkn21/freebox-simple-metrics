# Freebox Simple Metrics

Read-only Home Assistant custom integration for Freebox OS connection and switch metrics.

## What it exposes

Connection metrics:

- WAN state, media, type, IPv4, IPv6 and IPv4 port range
- Current upload/download rates
- Advertised upload/download bandwidth
- Upload/download byte counters
- FTTH link, SFP presence, signal, vendor, model, serial and optical power
- xDSL status, rates, SNR, attenuation and error counters when available

Switch metrics:

- Connected port count and total port count
- One connectivity binary sensor per switch port
- Per-port speed, mode, duplex and learned MAC count
- Per-port traffic/error counters when Freebox OS exposes port statistics

The integration has no Home Assistant actions, services, switches, buttons, selects or write entities.
It only reads Freebox OS API data after authentication.

## Installation with HACS

1. In HACS, add this repository as a custom integration repository.
2. Install `Freebox Simple Metrics`.
3. Restart Home Assistant.
4. Go to **Settings > Devices & services > Add integration**.
5. Search for `Freebox Simple Metrics`.

## Authentication

The normal setup flow does not ask for the Freebox admin password.

1. Enter the Freebox host, usually `192.168.1.254`.
   If your Freebox uses another LAN subnet, enter the matching address, for example `192.168.0.254`.
2. Submit the form.
3. Validate the authorization request on the Freebox Server display/button.
4. Submit the next Home Assistant form to finish setup.

Advanced users can enter an existing Freebox OS `app_token` with its matching `app_id`.
Leave the token empty for the normal authorization flow.

## Defaults

- Host: `192.168.1.254`
- Scan interval: `30` seconds
- Minimum scan interval: `5` seconds
- Timeout: `10` seconds
- App id: `fr.rkn21.freebox_simple_metrics`

## Repository layout

```text
custom_components/freebox_simple_metrics/
```

This is the only integration included in the repository, as expected by HACS.
