from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, found {count}")
    return text.replace(old, new, 1)


# ---- Public API: acquire/release an owned 512-frame buffer ---------------
p = Path("src/ds5_usb_audio.h")
s = p.read_text()
s = replace_once(s,
'''/**
 * Read accumulated PCM data when ready. Returns true if a full 512-sample
 * block is available. Output buffer must be at least
 * USB_AUDIO_ACCUM_SAMPLES * USB_AUDIO_CHANNELS * 2 bytes.
 * Called from audio_task context.
 */
bool usb_audio_read(int16_t *out);''',
'''/**
 * Acquire the newest complete 512-sample PCM frame without copying it.
 * The returned buffer is owned by the caller until usb_audio_release_frame().
 * At most one completed frame waits behind the currently consumed frame;
 * if the consumer falls behind, stale pending audio is dropped instead of
 * accumulating latency.
 */
const int16_t *usb_audio_acquire_frame(void);
void usb_audio_release_frame(const int16_t *frame);''',
"zero-copy header API")
p.write_text(s)


# ---- USB ISO producer: triple-buffer ownership instead of 4KB copy --------
p = Path("src/ds5_usb_audio.c")
s = p.read_text()
s = replace_once(s,
'''/* ---- Low-latency PCM frame ring ----
 * One buffer is being filled while up to two complete 512-sample frames
 * wait for audio_task. Memory use is lower than the old 2x1024 ping-pong. */
#define PCM_BUF_SAMPLES  USB_AUDIO_ACCUM_SAMPLES
#define PCM_BUF_BYTES    (PCM_BUF_SAMPLES * USB_AUDIO_CHANNELS * sizeof(int16_t))
#define PCM_BUF_COUNT    3
#define PCM_READY_MAX    (PCM_BUF_COUNT - 1)

static int16_t pcm_buf[PCM_BUF_COUNT][PCM_BUF_SAMPLES * USB_AUDIO_CHANNELS];
static volatile uint32_t pcm_write_pos = 0;
static volatile uint8_t  pcm_write_idx = 0;
static volatile uint8_t  pcm_read_idx = 0;
static volatile uint8_t  pcm_ready_count = 0;''',
'''/* ---- Zero-copy low-latency PCM ownership ring -------------------------
 * BL616 is single-core. Three 512-frame buffers are enough for exactly:
 *   1 WRITING in the USB ISO ISR + 1 READING in audio_task + 1 READY latest.
 * There is intentionally no deep FIFO: when the consumer falls behind, the
 * old READY frame is dropped and replaced by the newest completed frame.
 * This bounds latency and removes the old 4KB memcpy while interrupts were
 * disabled every 10.67ms. */
#define PCM_BUF_SAMPLES  USB_AUDIO_ACCUM_SAMPLES
#define PCM_BUF_COUNT    3
#define PCM_IDX_NONE     0xFF

enum pcm_owner_state {
    PCM_FREE = 0,
    PCM_WRITING,
    PCM_READY,
    PCM_READING,
};

static int16_t pcm_buf[PCM_BUF_COUNT][PCM_BUF_SAMPLES * USB_AUDIO_CHANNELS];
static volatile uint32_t pcm_write_pos = 0;
static volatile uint8_t  pcm_write_idx = 0;
static volatile uint8_t  pcm_ready_idx = PCM_IDX_NONE;
static volatile uint8_t  pcm_consumer_idx = PCM_IDX_NONE;
static volatile uint8_t  pcm_state[PCM_BUF_COUNT] = {
    PCM_WRITING, PCM_FREE, PCM_FREE
};

static void pcm_reset_stream_state(void)
{
    pcm_write_pos = 0;
    pcm_ready_idx = PCM_IDX_NONE;

    /* Never recycle a buffer currently owned by audio_task. A USB reset/open
     * may preempt that task; it will release the buffer when it resumes. */
    for (uint8_t i = 0; i < PCM_BUF_COUNT; i++) {
        if (pcm_state[i] != PCM_READING)
            pcm_state[i] = PCM_FREE;
    }

    uint8_t next = PCM_IDX_NONE;
    for (uint8_t i = 0; i < PCM_BUF_COUNT; i++) {
        if (pcm_state[i] == PCM_FREE) {
            next = i;
            break;
        }
    }
    if (next == PCM_IDX_NONE) {
        /* Impossible with one consumer and three buffers; recover safely. */
        next = 0;
        pcm_consumer_idx = PCM_IDX_NONE;
    }
    pcm_write_idx = next;
    pcm_state[next] = PCM_WRITING;
}''',
"PCM ownership declarations")

s = replace_once(s,
'''        if (pos >= PCM_BUF_SAMPLES * USB_AUDIO_CHANNELS) {
            pcm_write_pos = 0;

            BaseType_t woken = pdFALSE;
            if (pcm_ready_count < PCM_READY_MAX) {
                pcm_ready_count++;
                pcm_write_idx = (uint8_t)((pcm_write_idx + 1) % PCM_BUF_COUNT);
                xSemaphoreGiveFromISR(audio_sem, &woken);
            } else {
                /* Backlog full: discard oldest complete frame and keep
                 * the newest two instead of growing output latency. */
                pcm_read_idx = (uint8_t)((pcm_read_idx + 1) % PCM_BUF_COUNT);
                pcm_write_idx = (uint8_t)((pcm_write_idx + 1) % PCM_BUF_COUNT);
            }
            portYIELD_FROM_ISR(woken);
        } else {''',
'''        if (pos >= PCM_BUF_SAMPLES * USB_AUDIO_CHANNELS) {
            pcm_write_pos = 0;

            const uint8_t completed = pcm_write_idx;

            /* Latest-only pending policy. A READING frame is never touched. */
            if (pcm_ready_idx != PCM_IDX_NONE) {
                pcm_state[pcm_ready_idx] = PCM_FREE;
            }
            pcm_state[completed] = PCM_READY;
            pcm_ready_idx = completed;

            /* With 3 buffers and at most one READING + one READY, one FREE
             * buffer always exists for the next USB producer frame. */
            uint8_t next = PCM_IDX_NONE;
            for (uint8_t i = 0; i < PCM_BUF_COUNT; i++) {
                if (pcm_state[i] == PCM_FREE) {
                    next = i;
                    break;
                }
            }
            if (next == PCM_IDX_NONE) {
                /* Defensive recovery: drop the just-completed READY frame. */
                pcm_state[completed] = PCM_WRITING;
                pcm_ready_idx = PCM_IDX_NONE;
                next = completed;
            } else {
                pcm_state[next] = PCM_WRITING;
            }
            pcm_write_idx = next;

            BaseType_t woken = pdFALSE;
            (void)xSemaphoreGiveFromISR(audio_sem, &woken);
            portYIELD_FROM_ISR(woken);
        } else {''',
"PCM producer ownership handoff")

s = replace_once(s,
'''        stream_active = true;
        pcm_write_pos = 0;
        pcm_write_idx = 0;
        pcm_read_idx = 0;
        pcm_ready_count = 0;
        state_mgr_set_spk_active(true);''',
'''        stream_active = true;
        pcm_reset_stream_state();
        state_mgr_set_spk_active(true);''',
"stream open ownership reset")

s = replace_once(s,
'''void usb_audio_early_init(void)
{
    if (!audio_sem)
        audio_sem = xSemaphoreCreateCountingStatic(PCM_READY_MAX, 0, &audio_sem_buf);
}''',
'''void usb_audio_early_init(void)
{
    if (!audio_sem)
        audio_sem = xSemaphoreCreateBinaryStatic(&audio_sem_buf);
    pcm_reset_stream_state();
}''',
"binary audio semaphore")

s = replace_once(s,
'''    stream_active = false;
    pcm_write_pos = 0;
    pcm_write_idx = 0;
    pcm_read_idx = 0;
    pcm_ready_count = 0;
    state_mgr_set_spk_active(false);''',
'''    stream_active = false;
    pcm_reset_stream_state();
    state_mgr_set_spk_active(false);''',
"stream stop ownership reset")

s = replace_once(s,
'''bool usb_audio_read(int16_t *out)
{
    bool ok = false;

    /* Prevent the ISO ISR from recycling the selected 4KB frame while
     * it is copied. The critical section is tiny versus the 1ms USB
     * audio cadence and gives deterministic ring ownership. */
    taskENTER_CRITICAL();
    if (pcm_ready_count != 0) {
        uint8_t idx = pcm_read_idx;
        memcpy(out, pcm_buf[idx], PCM_BUF_BYTES);
        pcm_read_idx = (uint8_t)((pcm_read_idx + 1) % PCM_BUF_COUNT);
        pcm_ready_count--;
        ok = true;
    }
    taskEXIT_CRITICAL();
    return ok;
}''',
'''const int16_t *usb_audio_acquire_frame(void)
{
    const int16_t *frame = NULL;

    /* Only metadata is protected. The 4KB payload stays in-place and its
     * PCM_READING ownership prevents the ISR from recycling it. */
    taskENTER_CRITICAL();
    if (pcm_ready_idx != PCM_IDX_NONE && pcm_consumer_idx == PCM_IDX_NONE) {
        uint8_t idx = pcm_ready_idx;
        pcm_ready_idx = PCM_IDX_NONE;
        pcm_state[idx] = PCM_READING;
        pcm_consumer_idx = idx;
        frame = pcm_buf[idx];
    }
    taskEXIT_CRITICAL();
    return frame;
}

void usb_audio_release_frame(const int16_t *frame)
{
    if (!frame)
        return;

    taskENTER_CRITICAL();
    uint8_t idx = pcm_consumer_idx;
    if (idx != PCM_IDX_NONE && frame == pcm_buf[idx] &&
        pcm_state[idx] == PCM_READING) {
        pcm_state[idx] = PCM_FREE;
        pcm_consumer_idx = PCM_IDX_NONE;
    }
    taskEXIT_CRITICAL();
}''',
"zero-copy acquire release")

if "pcm_ready_count" in s or "PCM_READY_MAX" in s or "pcm_read_idx" in s:
    raise SystemExit("legacy PCM queue symbols remain after zero-copy transform")
p.write_text(s)


# ---- Audio task consumes the owned USB buffer in-place --------------------
p = Path("src/audio.c")
s = p.read_text()
s = replace_once(s,
'''static QueueHandle_t mic_queue;

static __attribute__((aligned(32))) int16_t pcm_block[ACCUM_SAMPLES * USB_AUDIO_CHANNELS];

static __attribute__((aligned(32))) int16_t spk_resamp[OPUS_FRAME_SAMPLES * 2];''',
'''static QueueHandle_t mic_queue;

static __attribute__((aligned(32))) int16_t spk_resamp[OPUS_FRAME_SAMPLES * 2];''',
"remove copied PCM block")

s = replace_once(s,
'''        if (xSemaphoreTake(sem, wait) == pdTRUE) {
            bool a_active = usb_audio_is_active();
            bool a_read   = a_active ? usb_audio_read(pcm_block) : false;
            bool a_bt     = bt_hid_host_get_state() == BT_HID_STATE_CONNECTED;

            if (a_active && a_read && a_bt)
            {''',
'''        if (xSemaphoreTake(sem, wait) == pdTRUE) {
            bool a_active = usb_audio_is_active();
            const int16_t *slot_pcm = a_active ? usb_audio_acquire_frame() : NULL;
            bool a_read   = slot_pcm != NULL;
            bool a_bt     = bt_hid_host_get_state() == BT_HID_STATE_CONNECTED;

            if (a_active && a_read && a_bt)
            {''',
"audio task zero-copy acquire")

s = replace_once(s,
'''                const int slot = audio_batch_count;
                const int16_t *slot_pcm = pcm_block;

#if LOG_LEVEL >= 3''',
'''                const int slot = audio_batch_count;

#if LOG_LEVEL >= 3''',
"remove local copied PCM alias")

s = replace_once(s,
'''            audio_frame_done:
                ;
            }
        }

        if (mic_status_pending &&''',
'''            audio_frame_done:
                ;
            }

            if (slot_pcm)
                usb_audio_release_frame(slot_pcm);
        }

        if (mic_status_pending &&''',
"audio task zero-copy release")

if "pcm_block" in s or "usb_audio_read(" in s:
    raise SystemExit("legacy copied PCM path remains in audio.c")
p.write_text(s)
print("BL616 zero-copy USB audio ownership patch applied")
