# Whisplay Bitcoin Market Dashboard

A real-time cryptocurrency market dashboard for the **Raspberry Pi Zero 2 W + Whisplay HAT**,
driven by the HAT's **single button** — or a **USB or Bluetooth keyboard**. No touchscreen, no SSH.

It is an **MFruit OS app**: it looks and handles like the rest of the device (MFruit OS status
bar, footer hints, fonts and controls, from the vendored MFruit App SDK in `mfruit_sdk/`). It
runs as a Whisplay **daemon app**: the `whisplay-daemon` service owns the LCD, backlight, RGB
LED and button, and this app draws into the shared framebuffer it hands out.

```
   +--------------------+
   | BTC/USD   ● ≋  82% |   page name · data light · WiFi · battery
   | $112,540.32        |
   | ▲ +2.41%    H / L  |   tap / Down    next page
   |      /\/\          |   2× / Up       previous page
   |  1H 4H 1D 1W 1Y    |   hold / Enter  next timeframe (refresh on other pages)
   | tap next  hold …   |   3× / R        refresh now
   +--------------------+   4× / Esc      leave the app
```

---

## 1. Hardware

| Item | Notes |
|---|---|
| Raspberry Pi Zero 2 W | Target platform; also runs on any 40-pin Pi |
| Whisplay HAT | 240x280 LCD, one push button, RGB LED |
| Wi-Fi | Required for market data (works offline from cache) |
| PiSugar battery | Optional |

The display is **240 x 280 px, RGB565**, exactly 134,400 bytes per frame.

### Pin usage (for reference)

The app never touches GPIO directly — the daemon owns the hardware. These are the HAT's
pins, taken from `Whisplay/runtime/whisplay.py`:

| Function | BOARD pin | BCM GPIO |
|---|---|---|
| LCD DC | 13 | GPIO27 |
| LCD RST | 7 | GPIO4 |
| Backlight | 15 | GPIO22 |
| **Button** | **11** | **GPIO17** |
| LED red | 22 | GPIO25 |
| LED green | 18 | GPIO24 |
| LED blue | 16 | GPIO23 |
| SPI MOSI / MISO / SCLK / CE0 | 19 / 21 / 23 / 24 | GPIO10 / 9 / 11 / 8 |

Buses used: **SPI** (LCD), **I2C + I2S** (audio, unused here).

> **Radxa Cubie A7Z warning** (from the Whisplay docs): the physical button is *not safe to
> press* on that board. This project is for the Raspberry Pi.

---

## 2. Install

Install the Whisplay daemon first, if it is not already running:

```bash
cd ~/Whisplay
./install_driver.sh                              # one time, reboot after
./daemon/install_whisplay_daemon_service.sh
```

Then install the dashboard:

```bash
cd ~/whisplay-crypto-dashboard
./install.sh                 # register as a daemon app
./install.sh --autostart     # ...and start automatically at boot
```

`install.sh` prefers **apt** packages for Pillow/numpy/requests — building those from source
with pip on a Pi Zero 2 W can take close to an hour.

No API key is required. The defaults use free, key-less endpoints.

Run it directly:

```bash
./run.sh
```

Or launch from the Whisplay desktop: single-click to select **BTC Dashboard**, then long press.
(Those are the *desktop's* gestures, set by the daemon. Once the app is running it uses its own
mapping — see Controls below.)

---

## 3. Controls

The controls are MFruit OS's, the same in every MFruit app and in the launcher itself
(`mfruit_sdk.input.InputController`):

| Button | Keyboard | Action |
|---|---|---|
| **tap** | Down, Right, Tab | Next page (Bitcoin > Market > Top > Statistics > System > Bitcoin) |
| **2×** | Up, Left | Previous page |
| **hold, then release** | Enter | The page's action: next chart timeframe (1H > 4H > 1D > 1W > 1Y) on the Bitcoin page, refresh on the others |
| **3×** | R | Refresh every data source now |
| **4×** | Esc | Leave the app, back to MFruit OS |
| | T | Next timeframe, from any page |
| | H, Home, 1–5 | Bitcoin page; page 1–5 |

A hold only *arms* after `long_press_ms`: the footer changes to **release to …** and nothing
happens until you let go. The footer always lists the gestures of the page you are on.

**Keyboard.** Plug in a USB keyboard or pair a Bluetooth one at any time; it is picked up within
two seconds. Keys act only while the dashboard is on screen — typing into another app never
reaches it.

### Why the app owns every gesture and the Esc key

The app registers with `exit_gesture: "none"` and `disable_esc_exit_key: true` (and claims the
Esc key again at start-up, because the Whisplay runtime client does not send that flag), so the
daemon reserves nothing: four clicks and Esc are handled in-app and leave cleanly.

Gesture timing is configurable in `config.yaml`:

```yaml
button:
  debounce_ms: 75        # contact bounce filter
  click_window_ms: 700   # window to collect further clicks
  long_press_ms: 700     # a hold arms here and acts on release
```

Four clicks fire **immediately** on the fourth release rather than waiting out the click
window, so leaving the app feels instant. Debounce is applied to the press edge only — gating
the release edge as well would swallow genuine short clicks, which are often only 30–60 ms long.

Raise `click_window_ms` if quick taps split into separate page changes instead of forming 2×,
3× or 4×; lower it if a tap feels sluggish (each one waits out the window before acting).

**Tuning it from real data.** Every gesture is logged with the measured gap between clicks:

```
gesture: quad   (gaps 37360/215/189/158 ms, window 700 ms)
gesture: single (gaps 1214 ms, window 700 ms)
```

Measured on the HAT's button, two clearly separated clusters emerged:

| Intent | Measured inter-click gap |
|---|---|
| Deliberate multi-click (double / quad) | **158–522 ms** |
| Ordinary browsing clicks | **≥ 1214 ms** |

`click_window_ms: 700` sits in the empty band between them, which is why `config.yaml` uses it.
400 ms was below the top of the deliberate cluster, so four intentional clicks kept
registering as four separate taps. If multi-click gestures are not forming
for you, read your own gaps out of the log and set the window between your two clusters.

---

## 4. The five pages

Every page has the MFruit OS status bar: the page name, a data light (green live, amber
refreshing, grey offline), WiFi and battery.

**1. Bitcoin (HOME)** — price, 24h change, 24h high/low, auto-scaling chart, window change,
volume (or the last-update time while offline), timeframe selector.

**2. Market Overview** — total market cap and its 24h change, total volume, BTC and ETH
dominance, stablecoin cap, Fear & Greed index with meter, BTC/ETH quotes.

**3. Top Cryptocurrencies** — top 4 by market cap: rank, symbol, market cap, price, 24h change.

**4. Bitcoin Statistics** — market cap, volume, 24h high/low, circulating and max supply,
all-time high, distance from ATH, 7d and 30d change, market-cap rank.

**5. System Status** — Wi-Fi / Internet / API checks, CPU, RAM, temperature, uptime, app
memory, last update, mode, and the last error message.

Any metric a provider does not return is **omitted entirely**. Nothing is faked or zero-filled.

---

## 5. Data providers

```
MarketDataProvider  (app/market/provider.py)
        |
        +-- BinanceProvider        price + candles, no key, fast
        +-- CoinGeckoProvider      market cap, supply, dominance, top coins
        +-- AlternativeMeProvider  Fear & Greed index
```

Each capability has its own ordered fallback list in `config.yaml`:

```yaml
providers:
  price: [binance, coingecko]     # first success wins
  chart: [binance, coingecko]
  market: [coingecko]
```

Binance is the default for price and charts (sub-second data, generous limits); CoinGecko
supplies everything an exchange ticker cannot know, such as market cap and supply.

**Adding a provider:** subclass `MarketDataProvider`, implement only the calls you can serve,
decorate with `@register_provider`, import it in `app/market/registry.py`, and add its name to
the relevant list in `config.yaml`. No UI code changes.

API keys are read from `.env` only, are never written to logs, and `.env` is git-ignored.

---

## 6. Offline behaviour

The last successful data is cached to `~/.whisplay-crypto/cache.json` and restored at boot, so
a Pi that starts without Internet still shows its last known market state.

Stale data is **never presented as live**:

| Indicator | Meaning |
|---|---|
| `● LIVE` (filled dot) | Data is current |
| `○ OFFLINE` (hollow ring) | The API is unreachable; the age of the data is shown |

Retries follow an exponential ladder — **5s, 10s, 30s, 60s, 120s** — per data lane, so a
rate-limited market call never slows the price tape. Any lane that fails keeps its previous
value rather than blanking the screen.

---

## 7. Configuration

Everything lives in `config.yaml`; no code changes needed. See the file for the full set.

```yaml
bitcoin:
  default_timeframe: 1D     # remembered across restarts

refresh:
  price_seconds: 10
  market_seconds: 60
  chart_seconds: 60

display:
  brightness: 80
  fps: 20                   # ceiling, not a target
  led_enabled: true         # LED shows market direction
```

The selected timeframe persists in `~/.whisplay-crypto/state.json`.

The RGB LED reports state at a glance: **green** up, **red** down, **amber** offline,
**blue** refreshing.

---

## 8. Architecture

```
whisplay-crypto-dashboard/
├── app/
│   ├── main.py              state machine, render loop, input actions
│   ├── board.py             daemon/direct/headless hardware acquisition
│   ├── ui/
│   │   ├── display.py       PIL canvas -> RGB565 framebuffer
│   │   ├── frame.py         a page inside the MFruit OS chrome (status bar, hints, toast)
│   │   ├── theme.py         palette, fonts, text fitting
│   │   ├── widgets.py       arrows, meters, panels
│   │   └── *_screen.py      the five pages
│   ├── market/
│   │   ├── provider.py      interface + data models
│   │   ├── binance.py  coingecko.py  alternative_me.py
│   │   ├── registry.py      provider registration
│   │   ├── service.py       scheduling, fallback, connection state
│   │   └── cache.py         persistent cache + app state
│   ├── chart/renderer.py    hand-rolled chart
│   ├── config/settings.py   defaults < config.yaml < environment
│   └── utils/               logger, format, network, system
├── mfruit_sdk/              MFruit App SDK (vendored copy; see mfruit_sdk/VENDORED)
├── tests/                   82 tests
├── tools/preview.py         render screens to PNG without hardware
└── packaging/               systemd unit + daemon app manifest
```

**Three threads, one job each:**

| Thread | Responsibility |
|---|---|
| `main` | Renders only. Never touches the network. |
| `market-service` | All HTTP. Publishes immutable snapshots. |
| `mfruit-gestures` | Button timing (MFruit App SDK). |
| `mfruit-keys` | USB / Bluetooth keyboards; idle until one is plugged in. |
| `mfruit-status` | WiFi level and battery for the status bar, every 10 s. |
| `foreground-retry` | Only when another app holds the screen; exits once granted. |

The render loop is **event-driven**: it sleeps on a condition variable until data changes, a
button is pressed, or the status tick expires. It redraws only when:

- new market data arrives
- the user changes page or timeframe
- the connection state changes
- the status tick fires (clock / data age)

Measured idle rate: **~9 redraws per minute**, not 20 per second.

---

## 9. Performance on a Pi Zero 2 W

Measured over 90 s of steady state with live data (x86 dev host; expect a few percent CPU on
Pi Zero silicon):

| Metric | Result | Target |
|---|---|---|
| CPU (idle) | 0.18% of one core | low |
| RSS memory | 52.6 MB | < 100 MB |
| Redraws | 8.7 / min | only on change |
| Threads | 4 | — |
| Frame size | 134,400 B | exact |

Recommendations:

- RGB565 conversion uses the MFruit App SDK's lookup-table converter (~11 ms per frame on a
  Pi Zero 2 W); numpy is no longer needed.
- **Use apt, not pip**, for Pillow.
- Keep `fps` at 20 or below; it matches the daemon's own refresh and is a ceiling, not a target.
- Do not lower `price_seconds` below ~5 s. It adds load and risks provider rate limits.
- Leave `cache_enabled: true`. Cache writes are throttled (30 s minimum) and atomic to limit
  SD-card wear.
- Logging is rotated at 512 KB x 3. Display redraws are deliberately never logged.
- The systemd unit sets `MemoryMax=180M` and `Nice=5`.
- Avoid running Chromium, Electron, X, or any browser-based dashboard alongside this.

---

## 10. Autostart

`./install.sh --autostart` installs `whisplay-crypto.service`:

```ini
After=network-online.target whisplay-daemon.service
BindsTo=whisplay-daemon.service
Restart=on-failure
RestartSec=5
StartLimitIntervalSec=0
```

**Why `on-failure` and not `always`:** the app exits cleanly when you click four times to
return to the Whisplay desktop. With `Restart=always`, systemd would relaunch it five seconds
later and take the screen back, making the exit gesture useless on a Pi that also runs other
Whisplay apps. `on-failure` still restarts after a crash, which is the actual requirement. If
your Pi is a dedicated single-purpose BTC display, change it to `always`.

**Starting while another app owns the screen:** if the dashboard starts while the Wi-Fi app (or
any other app) is in the foreground, the daemon refuses to hand over the framebuffer. The app
does not go blind — it reports mode `waiting`, keeps its data fresh, draws nothing, and retries
every 5 seconds. The moment the other app exits, the dashboard appears by itself.

`run.sh` waits up to 30 s for `/tmp/whisplay-daemon.sock` before starting, so boot does not
race the daemon. If the daemon never appears, the app falls back to direct hardware access.

```bash
sudo systemctl status  whisplay-crypto
sudo systemctl restart whisplay-crypto
journalctl -u whisplay-crypto -f
```

Boot sequence: `Pi > Wi-Fi > whisplay-daemon > run.sh waits for socket > dashboard (HOME)`.

---

## 11. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Blank screen, app appears to run | Check the mode on the System page. `WAITING` means another app owns the foreground — exit that app and this one appears within 5s. `HEADLESS` means the Whisplay runtime was not found — set `WHISPLAY_RUNTIME=/path/to/Whisplay/runtime`. |
| Log says `foreground unavailable ... retrying` | Expected. Another Whisplay app holds the screen; the dashboard takes over when that app exits. |
| Four clicks (or Esc) exit, then the app comes straight back | The unit is set to `Restart=always`. Change it to `Restart=on-failure` (the shipped default). |
| `whisplay runtime is unusable: No module named 'spidev'` | Whisplay drivers not installed. Run `Whisplay/install_driver.sh` and reboot. |
| App not on the Whisplay desktop | `ls ~/.whisplay-daemon/app/` should list `whisplay-crypto-dashboard.json`. Re-run `./install.sh`, then restart the daemon. |
| App exits while stepping through pages | Four taps inside the click window is the exit gesture. Tap at a slower pace, or lower `click_window_ms` in `config.yaml`. |
| Keyboard does nothing | Keys act only while the dashboard is on screen. Check the log for `keyboard connected: eventN`; the user running the app must be in the `input` group. |
| Holding the button exits instead of changing page | `exit_gesture` is not `none`. Confirm it in `~/.whisplay-daemon/app/whisplay-crypto-dashboard.json`, re-run `./install.sh`, and restart the daemon. |
| Clicks register as the wrong count | Tune `click_window_ms` (raise to 500 for slower clicking) and `debounce_ms` in `config.yaml`. |
| `OFFLINE` but the Pi has Internet | Check the System page's last error. A CoinGecko `429` is rate limiting — it backs off automatically; increase `market_seconds`/`top_seconds` if persistent. |
| Chart shows `CHART UNAVAILABLE` | Candles have not loaded yet, or Binance is unreachable in your region. Set `BINANCE_API_BASE` in `.env`, or put `coingecko` first in `providers.chart`. |
| Prices update, market cap does not | CoinGecko lane is failing while Binance succeeds. Expected degradation — the missing fields hide rather than showing stale numbers. |
| Nothing in `/var/log/whisplay-crypto/` | Directory not writable; logging fell back to `~/.whisplay-crypto/app.log`. |
| Service restarts repeatedly | `journalctl -u whisplay-crypto -n 50`. If the daemon is down, `BindsTo` stops this unit too. |
| Screen never updates | By design it only redraws on change. Press the button — if it responds, it is working. |

Useful checks:

```bash
tail -f /var/log/whisplay-crypto/app.log
tail -f ~/.whisplay-daemon/daemon-app.log
python3 -c "import socket,json;s=socket.socket(socket.AF_UNIX);s.connect('/tmp/whisplay-daemon.sock');s.sendall(b'{\"version\":1,\"cmd\":\"health.ping\",\"payload\":{}}\n');print(s.recv(4096))"
```

---

## 12. Development

```bash
python3 -m pytest tests/ -q          # 82 tests, no hardware needed
python3 tools/preview.py --mock      # render all five screens to PNG
python3 tools/preview.py             # ...with live market data
```

`tools/preview.py` writes each screen plus a contact sheet to `/tmp/whisplay-preview`, which
makes layout work possible without deploying to the Pi. Set
`MFRUIT_FONT_DIR=~/MFruitOS/assets/fonts` to preview with MFruit OS's font on a machine without
MFruit OS installed.

**MFruit App SDK.** `mfruit_sdk/` is a copy of MFruit OS's `mfruitos/sdk`: do not edit it
here. Change it in MFruit OS, then run `~/MFruitOS/scripts/sdk-sync.sh ~/whisplay-crypto-dashboard`
(`--check` reports a stale copy). The app's rules for MFruit OS are in
`.claude/rules/mfruit-os-app.md`.

---

## 13. Extending

The architecture is ready for:

- **More coins** — `CoinSummary` and the provider interface are already symbol-agnostic;
  `bitcoin.symbol` in `config.yaml` drives the whole app.
- **New pages** — subclass `Screen`, add it to `self.screens` in `main.py`. It joins the ring.
- **New providers** — see section 5.
- **Currency switching** — `bitcoin.currency` is threaded through formatting and both providers.

Deliberately out of scope for v1: portfolio tracking, price alerts, funding rates, ETF flows,
Telegram notifications, web configuration.

---

## 14. Security

- API keys live only in `.env`, which is `chmod 600` and git-ignored.
- Keys are attached as request headers and never logged; log lines carry provider names only.
- No inbound network listeners. All traffic is outbound HTTPS.
- The app talks to the daemon over a local Unix socket.

## License

Follows the license of the parent Whisplay project.
# whisplay-crypto-dashboard

## MFruit OS 1.4.0 keyboard compatibility

Vendored SDK 1.2.0 reads keys from MFruit OS's foreground key hub while the
launcher holds keyboards exclusively. Standalone use falls back to evdev.
Deploy this SDK with MFruit OS 1.4.0 so keyboard input continues to work.
