# Selectable latency modes

`low-latency` uses configuration version 4. The two new bytes are appended to
`struct config_body`, so the existing configuration prefix stays compatible.
Firmware migrates v2 -> v3 -> v4 without discarding valid existing settings.

## Input report mode (`input_report_mode`)

| Value | Name | Behavior |
|---:|---|---|
| 0 | `INPUT_REPORT_MODE_REALTIME_LATEST` | Low-latency latest-state mode. Stale queued BT/USB input reports are collapsed and the newest complete controller state wins. |
| 1 | `INPUT_REPORT_MODE_ORDERED_FIFO` | Compatibility mode. BT reports and USB IN reports use bounded 16-entry FIFO queues and preserve arrival order. On pathological overflow the newest report is dropped rather than rewriting older queued order. |

## Haptics latency mode (`haptic_latency_mode`)

| Value | Name | Speaker relationship | Haptics critical path |
|---:|---|---|---|
| 0 | `HAPTIC_LATENCY_BALANCED_1F` | Speaker lags haptics by one 512-sample source frame (~10.67 ms). This is the current low-latency BL616 behavior. | Frame-0 Opus is encoded during the first 10.67 ms window; after frame 1 arrives, haptics is submitted before frame-1 Opus encode. |
| 1 | `HAPTIC_LATENCY_LEGACY_SYNC` | Speaker and haptics stay time-aligned. | Both current Opus frames are encoded after the haptics pair is ready, then the 0x39 packet is submitted. This reproduces the original synchronized scheduling tradeoff. |
| 2 | `HAPTIC_LATENCY_MAX_2F` | Speaker lags by one complete two-frame 0x39 batch (~21.33 ms). | The current haptics pair is submitted before either current-batch Opus encode; both speaker frames are encoded afterward for the next packet. |

The DualSense Bluetooth audio report remains the standard 547-byte `0x39`
format containing two 64-byte haptics frames and, when speaker output is
active, two 200-byte Opus frames. The USB HID high-speed realtime polling
setting remains `bInterval = 3` (0.5 ms / 2000 Hz).

The existing HID configuration report (`0xF7`) transfers the packed
`config_body`; companion/configurator software can expose these two appended
bytes as dropdowns using the enum values above.
