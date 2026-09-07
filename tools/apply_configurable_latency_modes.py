from pathlib import Path


def replace_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected 1 match, found {n}")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# config.h: append mode fields so old serialized configs remain prefix-safe.
# ---------------------------------------------------------------------------
p = Path("src/config.h")
s = p.read_text()

s = replace_once(s,
'''/*
 * Configuration body — layout-compatible with DS5Dongle's Config_body
 * for potential companion-app interoperability.  Audio-related fields
 * are preserved but currently ignored on BL618.
 */
struct __attribute__((packed)) config_body {''',
'''/* Input delivery policy. Zero intentionally preserves the existing
 * low-latency branch behavior when migrating an older config. */
enum input_report_mode {
    INPUT_REPORT_MODE_REALTIME_LATEST = 0,
    INPUT_REPORT_MODE_ORDERED_FIFO    = 1,
};

/* Audio/haptics scheduler policy for the single-core BL616.
 * BALANCED_1F is the current low-latency implementation.
 * LEGACY_SYNC keeps speaker and haptics time-aligned and waits for both
 * current Opus frames before submitting 0x39.
 * MAX_HAPTICS_2F submits haptics before any current-batch Opus work and
 * therefore keeps speaker one whole 0x39 batch (~21.33 ms) behind. */
enum haptic_latency_mode {
    HAPTIC_LATENCY_BALANCED_1F = 0,
    HAPTIC_LATENCY_LEGACY_SYNC = 1,
    HAPTIC_LATENCY_MAX_2F      = 2,
};

/*
 * Configuration body — layout-compatible with the existing prefix. New
 * fields are appended only, so v2/v3 data can be migrated without losing
 * the user's existing settings.
 */
struct __attribute__((packed)) config_body {''',
"config enums")

s = replace_once(s,
'''    uint8_t tp_click_mode;        /* 0=touch triggers dirs, 1=click required */
    uint8_t battery_led;          /* bool — show battery level on player LEDs */
};

#define CONFIG_VERSION  3''',
'''    uint8_t tp_click_mode;        /* 0=touch triggers dirs, 1=click required */
    uint8_t battery_led;          /* bool — show battery level on player LEDs */
    uint8_t input_report_mode;    /* enum input_report_mode */
    uint8_t haptic_latency_mode;  /* enum haptic_latency_mode */
};

#define CONFIG_VERSION  4''',
"config tail/version")

s = replace_once(s,
'''static inline uint8_t config_audio_buf_len(void)    { return config_get()->audio_buffer_length; }
static inline bool config_usb_stealth(void)         { return config_get()->usb_stealth; }''',
'''static inline uint8_t config_audio_buf_len(void)    { return config_get()->audio_buffer_length; }
static inline uint8_t config_input_report_mode(void) { return config_get()->input_report_mode; }
static inline uint8_t config_haptic_latency_mode(void) { return config_get()->haptic_latency_mode; }
static inline bool config_usb_stealth(void)         { return config_get()->usb_stealth; }''',
"config accessors")
p.write_text(s)


# ---------------------------------------------------------------------------
# config.c: safe v2 -> v3 -> v4 migration and validation/defaults.
# ---------------------------------------------------------------------------
p = Path("src/config.c")
s = p.read_text()

old_migration = '''    if (b->config_version == 2) {
        b->headset_vol_offset = 0;
        b->lock_volume = (b->lock_volume == 1) ? 2 : 0;
        b->config_version = CONFIG_VERSION;
        LOG_INF("[CFG] Migrated v2→v3: lock_volume=%d\\n",
                b->lock_volume);
    } else if (b->config_version != CONFIG_VERSION) {
        LOG_WRN("[CFG] Version mismatch (%d vs %d), resetting\\n",
               b->config_version, CONFIG_VERSION);
        memset(b, 0xFF, sizeof(*b));
        b->config_version = CONFIG_VERSION;
    }
'''
new_migration = '''    if (b->config_version == 2) {
        b->headset_vol_offset = 0;
        b->lock_volume = (b->lock_volume == 1) ? 2 : 0;
        b->config_version = 3;
        LOG_INF("[CFG] Migrated v2->v3: lock_volume=%d\\n",
                b->lock_volume);
    }
    if (b->config_version == 3) {
        /* New tail bytes are zero after config_load()'s memset for old
         * serialized records. Set explicitly to document migration policy. */
        b->input_report_mode = INPUT_REPORT_MODE_REALTIME_LATEST;
        b->haptic_latency_mode = HAPTIC_LATENCY_BALANCED_1F;
        b->config_version = 4;
        LOG_INF("[CFG] Migrated v3->v4: input=realtime haptics=balanced-1f\\n");
    } else if (b->config_version != CONFIG_VERSION) {
        LOG_WRN("[CFG] Version mismatch (%d vs %d), resetting\\n",
               b->config_version, CONFIG_VERSION);
        memset(b, 0xFF, sizeof(*b));
        b->config_version = CONFIG_VERSION;
    }
'''
s = replace_once(s, old_migration, new_migration, "config migration")

s = replace_once(s,
'''    if (b->battery_led > 1)
        b->battery_led = 0;
}''',
'''    if (b->battery_led > 1)
        b->battery_led = 0;
    if (b->input_report_mode > INPUT_REPORT_MODE_ORDERED_FIFO)
        b->input_report_mode = INPUT_REPORT_MODE_REALTIME_LATEST;
    if (b->haptic_latency_mode > HAPTIC_LATENCY_MAX_2F)
        b->haptic_latency_mode = HAPTIC_LATENCY_BALANCED_1F;
}''',
"config validation")

s = replace_once(s,
'''        cfg.tp_mode_enabled_mask = 0x03; /* mode 0 + mode 1 enabled */
        cfg.tp_mouse_sensitivity = 8;
    }''',
'''        cfg.tp_mode_enabled_mask = 0x03; /* mode 0 + mode 1 enabled */
        cfg.tp_mouse_sensitivity = 8;
        cfg.input_report_mode = INPUT_REPORT_MODE_REALTIME_LATEST;
        cfg.haptic_latency_mode = HAPTIC_LATENCY_BALANCED_1F;
    }''',
"config defaults")

s = replace_once(s,
'''    LOG_INF("[CFG] tp_mode=%u mask=0x%02x sens=%u (rlen=%u)\\n",
           cfg.tp_mode, cfg.tp_mode_enabled_mask, cfg.tp_mouse_sensitivity,
           (unsigned)rlen);''',
'''    LOG_INF("[CFG] tp_mode=%u mask=0x%02x sens=%u (rlen=%u)\\n",
           cfg.tp_mode, cfg.tp_mode_enabled_mask, cfg.tp_mouse_sensitivity,
           (unsigned)rlen);
    LOG_INF("[CFG] input_mode=%u haptic_latency=%u\\n",
           cfg.input_report_mode, cfg.haptic_latency_mode);''',
"config mode log")
p.write_text(s)


# ---------------------------------------------------------------------------
# main.c: one queue supports latest-state and true ordered FIFO policies.
# ---------------------------------------------------------------------------
p = Path("src/main.c")
s = p.read_text()
s = replace_once(s,
'''#define INPUT_QUEUE_ITEM_SZ  DS5_BT_INPUT_REPORT_SIZE
#define USB_OUTPUT_BUF_SZ    64''',
'''#define INPUT_QUEUE_ITEM_SZ  DS5_BT_INPUT_REPORT_SIZE
#define INPUT_QUEUE_DEPTH    16  /* ~21 ms of BT reports at ~750 Hz */
#define USB_OUTPUT_BUF_SZ    64''',
"main input queue depth")

s = replace_once(s,
'''static volatile uint64_t out_isr_ts_us = 0;   /* timestamp set in USB ISR */
static volatile uint32_t out_drop_count = 0;   /* queue-full drops */''',
'''static volatile uint64_t out_isr_ts_us = 0;   /* timestamp set in USB ISR */
static volatile uint32_t out_drop_count = 0;   /* output queue-full drops */
static volatile uint32_t input_drop_count = 0; /* ordered input FIFO overflow */''',
"main input drop counter")

s = replace_once(s,
'''        /* xQueueOverwrite copies synchronously; avoid a redundant
         * stack buffer + memcpy in the BT -> USB hot path. */
        xQueueOverwrite(input_queue, data);''',
'''        if (config_input_report_mode() == INPUT_REPORT_MODE_ORDERED_FIFO) {
            /* Compatibility/ordered mode: preserve every BT report in arrival
             * order. If the bounded FIFO is ever full, drop the new report so
             * already queued temporal order is never rewritten. */
            if (xQueueSendToBack(input_queue, data, 0) != pdTRUE)
                input_drop_count++;
        } else {
            /* Realtime mode: collapse any queued stale reports, then publish
             * only the newest complete controller state. */
            uint8_t stale[INPUT_QUEUE_ITEM_SZ];
            while (xQueueReceive(input_queue, stale, 0) == pdTRUE) {}
            if (xQueueSendToBack(input_queue, data, 0) != pdTRUE)
                input_drop_count++;
        }''',
"main input enqueue policy")

s = replace_once(s,
'''    input_queue = xQueueCreate(1, INPUT_QUEUE_ITEM_SZ);
    /* Depth-1: USB ISR always delivers the latest report to usb_task.
     * The 10-deep app_tx_fifo in bt_hid_host.c provides the actual buffering
     * and CAN_SEND_NOW flow control (one BT packet in-flight at a time). */
    output_queue = xQueueCreate(5, USB_OUTPUT_BUF_SZ);''',
'''    input_queue = xQueueCreate(INPUT_QUEUE_DEPTH, INPUT_QUEUE_ITEM_SZ);
    /* Realtime mode drains this queue to newest-state semantics in the BT
     * callback. Ordered mode uses the same storage as a true FIFO. */
    output_queue = xQueueCreate(5, USB_OUTPUT_BUF_SZ);''',
"main input queue create")
p.write_text(s)


# ---------------------------------------------------------------------------
# usb_gamepad.c: preserve ordering all the way through the USB IN endpoint.
# ---------------------------------------------------------------------------
p = Path("src/usb_gamepad.c")
s = p.read_text()
old_pending = '''static volatile uint8_t pending_payload[DS5_USB_INPUT_PAYLOAD_LEN];
static volatile bool    pending_active = false;

ATTR_TCM_SECTION
static void try_send_pending(void)
{
    if (!pending_active || !usb_configured || ep_in_busy)
         return;
    /* Consume exactly one fresh report. Do not continuously pre-arm
     * the previous controller state after each IN completion. */
    ep_in_busy = true;
    pending_active = false;
    usb_in_buf[0] = DS5_USB_REPORT_ID_INPUT;
    memcpy(usb_in_buf + 1, (const void *)pending_payload,
           DS5_USB_INPUT_PAYLOAD_LEN);
    int ret = usbd_ep_start_write(0, USB_GAMEPAD_EP_IN, usb_in_buf, 64);
    if (ret < 0) {
        ep_in_busy = false;
        pending_active = true;
    } else if (!first_usb_send_logged) {
        first_usb_send_logged = true;
        LOG_INF("[USB] First input: [%02x %02x %02x %02x %02x %02x %02x %02x %02x %02x]\\n",
               usb_in_buf[0], usb_in_buf[1], usb_in_buf[2], usb_in_buf[3],
               usb_in_buf[4], usb_in_buf[5], usb_in_buf[6], usb_in_buf[7],
               usb_in_buf[8], usb_in_buf[9]);
    }
}
'''
new_pending = '''/* Realtime/latest mailbox plus an ordered FIFO. USB HS polls faster than
 * the controller's BT input rate, so FIFO occupancy should normally stay 0/1;
 * depth 16 only absorbs scheduler/host stalls without rewriting order. */
#define USB_INPUT_FIFO_DEPTH 16
static uint8_t pending_payload[DS5_USB_INPUT_PAYLOAD_LEN];
static volatile bool pending_active = false;
static uint8_t ordered_payload[USB_INPUT_FIFO_DEPTH][DS5_USB_INPUT_PAYLOAD_LEN];
static volatile uint8_t ordered_head = 0;
static volatile uint8_t ordered_tail = 0;
static volatile uint8_t input_report_mode_cached = INPUT_REPORT_MODE_REALTIME_LATEST;
static volatile uint32_t ordered_input_drop_count = 0;

static inline void reset_input_tx_state(void)
{
    pending_active = false;
    ordered_head = 0;
    ordered_tail = 0;
}

ATTR_TCM_SECTION
static void try_send_pending(void)
{
    if (!usb_configured || ep_in_busy)
        return;

    bool ordered = (input_report_mode_cached == INPUT_REPORT_MODE_ORDERED_FIFO);
    uint8_t fifo_head = ordered_head;
    if (ordered) {
        if (fifo_head == ordered_tail)
            return;
    } else if (!pending_active) {
        return;
    }

    ep_in_busy = true;
    usb_in_buf[0] = DS5_USB_REPORT_ID_INPUT;

    if (ordered) {
        memcpy(usb_in_buf + 1, ordered_payload[fifo_head],
               DS5_USB_INPUT_PAYLOAD_LEN);
        /* Consume before arming the endpoint so a very fast completion IRQ
         * cannot observe the same FIFO element twice. Roll back on failure. */
        ordered_head = (uint8_t)((fifo_head + 1) % USB_INPUT_FIFO_DEPTH);
    } else {
        /* Consume exactly one fresh report. New BT states arriving while USB
         * is busy overwrite the mailbox, preserving latest-state semantics. */
        pending_active = false;
        memcpy(usb_in_buf + 1, pending_payload, DS5_USB_INPUT_PAYLOAD_LEN);
    }

    int ret = usbd_ep_start_write(0, USB_GAMEPAD_EP_IN, usb_in_buf, 64);
    if (ret < 0) {
        ep_in_busy = false;
        if (ordered)
            ordered_head = fifo_head;
        else
            pending_active = true;
    } else if (!first_usb_send_logged) {
        first_usb_send_logged = true;
        LOG_INF("[USB] First input: [%02x %02x %02x %02x %02x %02x %02x %02x %02x %02x]\\n",
               usb_in_buf[0], usb_in_buf[1], usb_in_buf[2], usb_in_buf[3],
               usb_in_buf[4], usb_in_buf[5], usb_in_buf[6], usb_in_buf[7],
               usb_in_buf[8], usb_in_buf[9]);
    }
}
'''
s = replace_once(s, old_pending, new_pending, "USB input scheduler")

# Flush pending input on bus lifecycle transitions; never replay old ordered
# reports after enumeration/reset/suspend/disconnect.
s = replace_once(s,
'''    case USBD_EVENT_CONFIGURED:
        usb_configured = true;
        ep_in_busy = false;
        kbd_ep_busy = false;''',
'''    case USBD_EVENT_CONFIGURED:
        usb_configured = true;
        ep_in_busy = false;
        kbd_ep_busy = false;
        reset_input_tx_state();''',
"USB configured flush")
s = replace_once(s,
'''    case USBD_EVENT_RESET:
        usb_configured = false;
        ep_in_busy = false;
        kbd_ep_busy = false;''',
'''    case USBD_EVENT_RESET:
        usb_configured = false;
        ep_in_busy = false;
        kbd_ep_busy = false;
        reset_input_tx_state();''',
"USB reset flush")
s = replace_once(s,
'''    case USBD_EVENT_SUSPEND:
        usb_configured = false;
        ep_in_busy = false;
        kbd_ep_busy = false;''',
'''    case USBD_EVENT_SUSPEND:
        usb_configured = false;
        ep_in_busy = false;
        kbd_ep_busy = false;
        reset_input_tx_state();''',
"USB suspend flush")
s = replace_once(s,
'''    case USBD_EVENT_DISCONNECTED:
        LOG_INF("[USB-EVT] DISCONNECTED (VBUS lost)\\n");''',
'''    case USBD_EVENT_DISCONNECTED:
        reset_input_tx_state();
        LOG_INF("[USB-EVT] DISCONNECTED (VBUS lost)\\n");''',
"USB disconnect flush")

s = replace_once(s,
'''ATTR_TCM_SECTION
int usb_gamepad_send_raw_input(const uint8_t *payload)
{
    /* Publish only after the newest report has been copied completely.
     * If an IN-completion IRQ fires during memcpy it sees no pending report. */
    pending_active = false;
    memcpy((void *)pending_payload, payload, DS5_USB_INPUT_PAYLOAD_LEN);
    pending_active = true;
    try_send_pending();
    return 0;
}''',
'''ATTR_TCM_SECTION
int usb_gamepad_send_raw_input(const uint8_t *payload)
{
    uint8_t mode = config_input_report_mode();
    int ret = 0;

    /* Producer runs in task context. Keep the publish section short so the
     * USB IN completion IRQ can never consume a half-written report. */
    taskENTER_CRITICAL();
    if (mode != input_report_mode_cached) {
        reset_input_tx_state();
        input_report_mode_cached = mode;
    }

    if (mode == INPUT_REPORT_MODE_ORDERED_FIFO) {
        uint8_t tail = ordered_tail;
        uint8_t next = (uint8_t)((tail + 1) % USB_INPUT_FIFO_DEPTH);
        if (next == ordered_head) {
            ordered_input_drop_count++;
            ret = -1;
        } else {
            memcpy(ordered_payload[tail], payload, DS5_USB_INPUT_PAYLOAD_LEN);
            ordered_tail = next; /* publish only after full copy */
        }
    } else {
        pending_active = false;
        memcpy(pending_payload, payload, DS5_USB_INPUT_PAYLOAD_LEN);
        pending_active = true;
    }
    taskEXIT_CRITICAL();

    if (ret == 0)
        try_send_pending();
    return ret;
}''',
"USB send mode policy")
p.write_text(s)


# ---------------------------------------------------------------------------
# audio.c: 3 distinct single-core policies.
# ---------------------------------------------------------------------------
p = Path("src/audio.c")
s = p.read_text()

s = replace_once(s,
'''static uint8_t  audio_batch_count;
static bool     audio_batch_speaker;
static bool     audio_batch_headset;
static int      audio_batch_channels;
/* BL616 is single-core: keep speaker one 10.67ms source frame behind haptics.
 * opus_slots[0] is the previous encoded frame (lag), opus_slots[1] is the
 * first frame of the current haptics batch. The second current speaker frame
 * is encoded only AFTER the current haptics packet has been submitted. */
static bool     speaker_pipeline_primed;''',
'''static uint8_t  audio_batch_count;
static bool     audio_batch_speaker;
static bool     audio_batch_headset;
static int      audio_batch_channels;
static uint8_t  audio_batch_latency_mode;
/* Frame 0 must survive release of the zero-copy USB buffer in legacy-sync and
 * max-haptics modes, where its Opus encode is deliberately deferred. */
static __attribute__((aligned(32))) int16_t speaker_frame0_stage[ACCUM_SAMPLES * USB_AUDIO_CHANNELS];
/* Lagged modes use cached valid Opus packets until a previous speaker frame
 * exists for the current route/channel configuration. */
static bool     speaker_pipeline_primed;''',
"audio batch state")

s = replace_once(s,
'''static void prime_speaker_pipeline(int channels)
{
    const uint8_t *silence = (channels == 2)
                           ? opus_silence_stereo : opus_silence_mono;
    memcpy(opus_slots[0], silence, OPUS_OUT_SIZE);
    speaker_pipeline_primed = true;
}''',
'''static void prime_speaker_pipeline(int channels)
{
    const uint8_t *silence = (channels == 2)
                           ? opus_silence_stereo : opus_silence_mono;
    /* Prime both positions: balanced-1f needs slot 0, max-2f needs both. */
    memcpy(opus_slots[0], silence, OPUS_OUT_SIZE);
    memcpy(opus_slots[1], silence, OPUS_OUT_SIZE);
    speaker_pipeline_primed = true;
}''',
"audio prime both")

# Capture selected policy next to the existing audio-haptic source mode.
s = replace_once(s,
'''                uint8_t ah_mode = config_get()->audio_haptic;


#if LOG_LEVEL >= 3''',
'''                uint8_t ah_mode = config_get()->audio_haptic;
                uint8_t latency_mode = config_haptic_latency_mode();

#if LOG_LEVEL >= 3''',
"audio latency mode read")

old_sched = '''                /* DS5_Bridge-style producer separation: process one 512-sample
                   USB frame as soon as it is complete. The Bluetooth 0x39 format
                   remains a two-frame compositor. */
                if (audio_batch_count != 0 &&
                    (audio_batch_speaker != speaker_on ||
                     audio_batch_headset != plug_headset ||
                     audio_batch_channels != target_channels)) {
                    audio_batch_count = 0;
                    speaker_pipeline_primed = false;
                }
                if (!speaker_on)
                    speaker_pipeline_primed = false;
                if (speaker_on && !speaker_pipeline_primed)
                    prime_speaker_pipeline(target_channels);
                if (audio_batch_count == 0) {
                    audio_batch_speaker = speaker_on;
                    audio_batch_headset = plug_headset;
                    audio_batch_channels = target_channels;
                }

                const int slot = audio_batch_count;

#if LOG_LEVEL >= 3
                uint64_t t_hap0 = bflb_mtimer_get_time_us();
#endif
                if (ah_mode == 2) {
                    audio_to_haptic(slot_pcm, haptic_slots[slot], ACCUM_SAMPLES);
                } else if (ah_mode == 1 &&
                           haptic_channel_silent(slot_pcm, ACCUM_SAMPLES)) {
                    audio_to_haptic(slot_pcm, haptic_slots[slot], ACCUM_SAMPLES);
                } else {
                    decimate_haptics(slot_pcm, haptic_slots[slot], ACCUM_SAMPLES);
                }
#if LOG_LEVEL >= 3
                prof_haptic += bflb_mtimer_get_time_us() - t_hap0;
#endif

                /* BL616 single-core haptics-first scheduler.
                 * Frame 0: encode speaker immediately during the 10.67ms slack.
                 * Frame 1: DO NOT encode yet. The current haptics pair is now
                 * complete, so submit it first with [previous speaker, frame0].
                 * Frame 1 speaker is encoded after BT submission and becomes
                 * the previous frame for the next batch. */
                if (speaker_on && slot == 0) {
#if LOG_LEVEL >= 3
                    uint64_t t_op0 = bflb_mtimer_get_time_us();
#endif
                    encode_speaker_frame(slot_pcm, opus_slots[1]);
#if LOG_LEVEL >= 3
                    prof_opus += bflb_mtimer_get_time_us() - t_op0;
#endif
                }

                audio_batch_count++;
                if (audio_batch_count < AUDIO_BATCH_FRAMES)
                    goto audio_frame_done;

                /* Both haptic slots are ready. Do not insert the old fixed 1ms
                 * mic delay; mic decode already runs in its own FreeRTOS task. */
                audio_batch_count = 0;

#if LOG_LEVEL >= 3
                uint64_t t_send0 = bflb_mtimer_get_time_us();
#endif
                int send_ret = send_audio_report(audio_batch_speaker, audio_batch_headset);'''

new_sched = '''                /* Process one 512-sample USB frame at a time. The DualSense
                 * 0x39 transport remains a two-frame compositor; only speaker
                 * scheduling changes between the selectable policies. */
                if (audio_batch_count != 0 &&
                    (audio_batch_speaker != speaker_on ||
                     audio_batch_headset != plug_headset ||
                     audio_batch_channels != target_channels ||
                     audio_batch_latency_mode != latency_mode)) {
                    audio_batch_count = 0;
                    speaker_pipeline_primed = false;
                }

                if (!speaker_on || latency_mode == HAPTIC_LATENCY_LEGACY_SYNC) {
                    speaker_pipeline_primed = false;
                } else if (!speaker_pipeline_primed) {
                    prime_speaker_pipeline(target_channels);
                }

                if (audio_batch_count == 0) {
                    audio_batch_speaker = speaker_on;
                    audio_batch_headset = plug_headset;
                    audio_batch_channels = target_channels;
                    audio_batch_latency_mode = latency_mode;
                }

                const int slot = audio_batch_count;

#if LOG_LEVEL >= 3
                uint64_t t_hap0 = bflb_mtimer_get_time_us();
#endif
                if (ah_mode == 2) {
                    audio_to_haptic(slot_pcm, haptic_slots[slot], ACCUM_SAMPLES);
                } else if (ah_mode == 1 &&
                           haptic_channel_silent(slot_pcm, ACCUM_SAMPLES)) {
                    audio_to_haptic(slot_pcm, haptic_slots[slot], ACCUM_SAMPLES);
                } else {
                    decimate_haptics(slot_pcm, haptic_slots[slot], ACCUM_SAMPLES);
                }
#if LOG_LEVEL >= 3
                prof_haptic += bflb_mtimer_get_time_us() - t_hap0;
#endif

                if (speaker_on && slot == 0) {
                    if (latency_mode == HAPTIC_LATENCY_BALANCED_1F) {
                        /* Current low-latency policy: encode frame 0 during the
                         * first 10.67ms window. At send time speaker contains
                         * [previous frame1, current frame0]. */
#if LOG_LEVEL >= 3
                        uint64_t t_op0 = bflb_mtimer_get_time_us();
#endif
                        encode_speaker_frame(slot_pcm, opus_slots[1]);
#if LOG_LEVEL >= 3
                        prof_opus += bflb_mtimer_get_time_us() - t_op0;
#endif
                    } else {
                        /* Legacy-sync and max-2f intentionally defer frame 0
                         * encoding; retain PCM after zero-copy USB release. */
                        memcpy(speaker_frame0_stage, slot_pcm,
                               sizeof(speaker_frame0_stage));
                    }
                }

                audio_batch_count++;
                if (audio_batch_count < AUDIO_BATCH_FRAMES)
                    goto audio_frame_done;

                audio_batch_count = 0;

                if (speaker_on && latency_mode == HAPTIC_LATENCY_LEGACY_SYNC) {
                    /* Original-style synchronized policy: both current speaker
                     * frames are encoded only after the haptics pair is ready.
                     * This keeps speaker/haptics aligned but puts both Opus
                     * encodes on the haptics critical path. */
#if LOG_LEVEL >= 3
                    uint64_t t_op_legacy = bflb_mtimer_get_time_us();
#endif
                    encode_speaker_frame(speaker_frame0_stage, opus_slots[0]);
                    encode_speaker_frame(slot_pcm, opus_slots[1]);
#if LOG_LEVEL >= 3
                    prof_opus += bflb_mtimer_get_time_us() - t_op_legacy;
#endif
                }

#if LOG_LEVEL >= 3
                uint64_t t_send0 = bflb_mtimer_get_time_us();
#endif
                int send_ret = send_audio_report(audio_batch_speaker, audio_batch_headset);'''
s = replace_once(s, old_sched, new_sched, "audio selectable scheduler")

old_post = '''#endif
                if (speaker_on) {
                    /* Current haptics are already in the Bluetooth stack. */
                    encode_speaker_frame(slot_pcm, opus_slots[0]);
                    speaker_pipeline_primed = true;
                }
            audio_frame_done:
                ;'''
new_post = '''#endif
                if (speaker_on) {
                    if (latency_mode == HAPTIC_LATENCY_BALANCED_1F) {
                        /* Current haptics are already submitted. Frame 1 is the
                         * lag frame for the next 0x39 packet. */
                        encode_speaker_frame(slot_pcm, opus_slots[0]);
                        speaker_pipeline_primed = true;
                    } else if (latency_mode == HAPTIC_LATENCY_MAX_2F) {
                        /* Maximum haptics priority: neither current speaker
                         * frame is allowed onto the haptics critical path.
                         * Encode the just-sent batch afterward for next 0x39. */
                        encode_speaker_frame(speaker_frame0_stage, opus_slots[0]);
                        encode_speaker_frame(slot_pcm, opus_slots[1]);
                        speaker_pipeline_primed = true;
                    }
                }
            audio_frame_done:
                ;'''
s = replace_once(s, old_post, new_post, "audio deferred speaker policies")

p.write_text(s)

# Static sanity checks. Keep the requested HID 2000Hz interval unchanged.
checks = {
    "src/config.h": [
        "#define CONFIG_VERSION  4",
        "INPUT_REPORT_MODE_ORDERED_FIFO",
        "HAPTIC_LATENCY_MAX_2F",
    ],
    "src/main.c": ["INPUT_QUEUE_DEPTH    16", "xQueueSendToBack(input_queue"],
    "src/usb_gamepad.c": ["USB_INPUT_FIFO_DEPTH 16", "INPUT_REPORT_MODE_ORDERED_FIFO"],
    "src/audio.c": ["HAPTIC_LATENCY_LEGACY_SYNC", "HAPTIC_LATENCY_MAX_2F", "speaker_frame0_stage"],
}
for name, needles in checks.items():
    text = Path(name).read_text()
    for needle in needles:
        if needle not in text:
            raise SystemExit(f"missing sanity marker {needle!r} in {name}")

usb = Path("src/usb_gamepad.c").read_text()
if "default: interval = 3; break;" not in usb:
    raise SystemExit("HS realtime polling interval changed; expected bInterval=3")

print("configurable input/haptics latency modes applied")
