# WiFi Auto-Reconnect Failure (Mar 20–28, 2026)

## Symptom

The cron job (`run_cron.sh`, every 2 hours) stopped producing logs after Mar 20 02:17.
The `nc -zw1 google.com 443` network check in `run.sh` was failing, causing the script
to exit immediately before reaching the Python execution.

## Root Cause

1. **WiFi dropped** on Mar 20 ~03:11 — the router SSID became temporarily
   unreachable (`ssid-not-found`).

2. NetworkManager attempted to reconnect. During the WPA 4-way handshake, the connection
   failed again. NM interpreted this as a **wrong password** and transitioned to
   `need-auth` state, requesting new credentials from a GNOME Shell secret agent.

3. **No secret agent was available** (screen locked / no active GUI session), so NM
   failed with `no-secrets`:
   ```
   device (<wifi-iface>): no secrets: No agents were available for this request.
   device (<wifi-iface>): state change: need-auth -> failed (reason 'no-secrets')
   ```

4. After exhausting `autoconnect-retries` (default: **4 attempts**), NM gave up
   permanently. The WiFi interface went `inactive` and **never retried** — even after
   the router came back online.

5. WiFi only reconnected 8 days later (Mar 28 20:14) when a GUI login started the
   GNOME Shell NetworkAgent, which unblocked the stored credentials.

## Fix Applied

### 1. Unlimited autoconnect retries

```bash
sudo nmcli connection modify <SSID> connection.autoconnect-retries 0
```

NM will now retry indefinitely instead of giving up after 4 failures.

### 2. Dispatcher script for forced reconnect

Created `/etc/NetworkManager/dispatcher.d/99-wifi-reconnect`:

```sh
#!/bin/sh

IFACE="$1"
ACTION="$2"

if [ "$IFACE" = "<wifi-iface>" ] && [ "$ACTION" = "down" ]; then
    sleep 10
    STATE=$(nmcli -t -f STATE general status 2>/dev/null)
    if [ "$STATE" != "connected" ]; then
        logger -t wifi-reconnect "WiFi down, attempting reconnect"
        nmcli connection up <SSID> 2>/dev/null
    fi
fi
```

When the WiFi interface goes down, this waits 10 seconds then forces a reconnect via
`nmcli connection up`, which uses the stored PSK directly — bypassing the secret agent
requirement.

### 3. Cron output redirection (debug aid)

The crontab entry was updated to capture output for future debugging:

```
0 */2 * * * /path/to/run_cron.sh >> /tmp/naverpaper_cron_debug.log 2>&1
```

Previously, cron output was silently lost (no mail system installed).
