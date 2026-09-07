from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, found {count}")
    return text.replace(old, new, 1)


# Low-latency controller-side buffer default. Existing explicitly saved values
# remain configurable; new/factory-reset configs start at the protocol minimum.
p = Path("src/config.c")
s = p.read_text()
s = replace_once(s,
    "if (b->audio_buffer_length < 16 || b->audio_buffer_length > 128)\n        b->audio_buffer_length = 64;",
    "if (b->audio_buffer_length < 16 || b->audio_buffer_length > 128)\n        b->audio_buffer_length = 16;",
    "audio buffer validation default")
s = replace_once(s,
    "cfg.audio_buffer_length = 64;",
    "cfg.audio_buffer_length = 16;",
    "audio buffer factory default")
p.write_text(s)


p = Path("src/audio.c")
s = p.read_text()

s = replace_once(s,
'''static __attribute__((aligned(32))) uint8_t  opus_slots[AUDIO_BATCH_FRAMES][OPUS_OUT_SIZE];
static __attribute__((aligned(32))) int8_t   haptic_slots[AUDIO_BATCH_FRAMES][HAPTIC_BUF_SIZE];
static uint8_t  audio_batch_count;
static bool     audio_batch_speaker;
static bool     audio_batch_headset;
static int      audio_batch_channels;

static bool     silence_ready;''',
'''static __attribute__((aligned(32))) uint8_t  opus_slots[AUDIO_BATCH_FRAMES][OPUS_OUT_SIZE];
static __attribute__((aligned(32))) int8_t   haptic_slots[AUDIO_BATCH_FRAMES][HAPTIC_BUF_SIZE];
/* Cached valid Opus silence for haptics-first speaker priming. */
static __attribute__((aligned(32))) uint8_t  opus_silence_mono[OPUS_OUT_SIZE];
static __attribute__((aligned(32))) uint8_t  opus_silence_stereo[OPUS_OUT_SIZE];
static uint8_t  audio_batch_count;
static bool     audio_batch_speaker;
static bool     audio_batch_headset;
static int      audio_batch_channels;
/* BL616 is single-core: keep speaker one 10.67ms source frame behind haptics.
 * opus_slots[0] is the previous encoded frame (lag), opus_slots[1] is the
 * first frame of the current haptics batch. The second current speaker frame
 * is encoded only AFTER the current haptics packet has been submitted. */
static bool     speaker_pipeline_primed;

static bool     silence_ready;''',
"speaker pipeline state")

# Insert reusable Opus helpers immediately before the haptics section.
anchor = '''/* ---- Haptics: 16:1 point-sample decimation (stereo int16 → stereo int8) ----'''
if anchor not in s:
    raise SystemExit("haptics helper insertion anchor not found")
helpers = r'''/* Pad a CELT/Opus packet to the fixed 200-byte DualSense block. */
static void opus_pad_fixed(uint8_t *dst, int encoded)
{
    if (encoded <= 0) {
        memset(dst, 0, OPUS_OUT_SIZE);
        return;
    }
    if (encoded < OPUS_OUT_SIZE) {
        int pad_ret = opus_packet_pad(dst, encoded, OPUS_OUT_SIZE);
        if (pad_ret != OPUS_OK)
            memset(dst + encoded, 0, OPUS_OUT_SIZE - encoded);
    }
}

/* Encode one 512-sample USB source frame into one 10ms / 200-byte block. */
static int encode_speaker_frame(const int16_t *slot_pcm, uint8_t *dst)
{
    deinterleave_4ch(slot_pcm, ACCUM_SAMPLES);
    int mono = (encoder_channels == 1);
    resample_512_480(slot_pcm, spk_resamp, mono);

    encode_start_us = bflb_mtimer_get_time_us();
    encoding_in_progress = true;
    int encoded = opus_encode(encoder, spk_resamp, OPUS_FRAME_SAMPLES,
                              dst, OPUS_OUT_SIZE);
    encoding_in_progress = false;

    if (encoder_reset_pending) {
        encoder_reset_pending = false;
        opus_encoder_ctl(encoder, OPUS_RESET_STATE);
        speaker_pipeline_primed = false;
    }
    if (encoded <= 0)
        LOG_ERR("[AUDIO] Opus encode error: %d\n", encoded);
    opus_pad_fixed(dst, encoded);
    return encoded;
}

static void prime_speaker_pipeline(int channels)
{
    const uint8_t *silence = (channels == 2)
                           ? opus_silence_stereo : opus_silence_mono;
    memcpy(opus_slots[0], silence, OPUS_OUT_SIZE);
    speaker_pipeline_primed = true;
}

'''
s = s.replace(anchor, helpers + anchor, 1)

# Prediction is deliberately disabled in the low-latency branch. Besides
# lowering CELT CPU work, it makes the cached silence primer safe across
# encoder resets/reinitialization because packets do not depend on inter-frame
# prediction history.
s = s.replace('opus_encoder_ctl(encoder, OPUS_SET_PREDICTION_DISABLED(0));',
              'opus_encoder_ctl(encoder, OPUS_SET_PREDICTION_DISABLED(1));')
s = s.replace('/* 1ch (no headset): full quality — prediction enabled, full bandwidth */',
              '/* 1ch (no headset): low-latency CELT — prediction disabled */')

# Precompute valid mono/stereo silence packets once at boot, then restore the
# normal mono encoder. This avoids an extra Opus encode on the first realtime
# haptics batch or after a stream reset.
init_anchor = '''    opus_encoder_ctl(encoder, OPUS_SET_COMPLEXITY(0));
    /* 1ch (no headset): low-latency CELT — prediction disabled */
    encoder_channels = 1;'''
init_new = '''    opus_encoder_ctl(encoder, OPUS_SET_COMPLEXITY(0));
    opus_encoder_ctl(encoder, OPUS_SET_PREDICTION_DISABLED(1));

    /* Build valid fixed-size silence primers outside the realtime path. */
    memset(spk_resamp, 0, sizeof(spk_resamp));
    int silence_encoded = opus_encode(encoder, spk_resamp,
                                      OPUS_FRAME_SAMPLES,
                                      opus_silence_mono, OPUS_OUT_SIZE);
    opus_pad_fixed(opus_silence_mono, silence_encoded);

    if (opus_encoder_init(encoder, 48000, 2,
                          OPUS_APPLICATION_RESTRICTED_CELT) == OPUS_OK) {
        opus_encoder_ctl(encoder, OPUS_SET_EXPERT_FRAME_DURATION(OPUS_FRAMESIZE_10_MS));
        opus_encoder_ctl(encoder, OPUS_SET_BITRATE(128000));
        opus_encoder_ctl(encoder, OPUS_SET_VBR(1));
        opus_encoder_ctl(encoder, OPUS_SET_COMPLEXITY(0));
        opus_encoder_ctl(encoder, OPUS_SET_PREDICTION_DISABLED(1));
        silence_encoded = opus_encode(encoder, spk_resamp,
                                      OPUS_FRAME_SAMPLES,
                                      opus_silence_stereo, OPUS_OUT_SIZE);
        opus_pad_fixed(opus_silence_stereo, silence_encoded);
    } else {
        memset(opus_silence_stereo, 0, sizeof(opus_silence_stereo));
    }

    /* Restore the normal startup encoder after building the primers. */
    err = opus_encoder_init(encoder, 48000, 1,
                            OPUS_APPLICATION_RESTRICTED_CELT);
    if (err != OPUS_OK) {
        LOG_ERR("[AUDIO] Opus encoder restore failed: %d\\n", err);
        return -1;
    }
    opus_encoder_ctl(encoder, OPUS_SET_EXPERT_FRAME_DURATION(OPUS_FRAMESIZE_10_MS));
    opus_encoder_ctl(encoder, OPUS_SET_BITRATE(160000));
    opus_encoder_ctl(encoder, OPUS_SET_VBR(1));
    opus_encoder_ctl(encoder, OPUS_SET_COMPLEXITY(0));
    opus_encoder_ctl(encoder, OPUS_SET_PREDICTION_DISABLED(1));

    /* 1ch (no headset): low-latency CELT — prediction disabled */
    encoder_channels = 1;'''
s = replace_once(s, init_anchor, init_new, "silence primer init")

# Reset pipeline state wherever the batch is reset.
s = replace_once(s,
'''    audio_batch_count = 0;
    audio_batch_speaker = false;
    audio_batch_headset = false;
    audio_batch_channels = 1;''',
'''    audio_batch_count = 0;
    audio_batch_speaker = false;
    audio_batch_headset = false;
    audio_batch_channels = 1;
    speaker_pipeline_primed = false;''',
"audio init pipeline reset")

# Watchdog respawn loses codec history; reprime on the next frame.
s = replace_once(s,
'''    audio_task_killed = false;
    audio_batch_count = 0;''',
'''    audio_task_killed = false;
    audio_batch_count = 0;
    speaker_pipeline_primed = false;''',
"watchdog pipeline reset")

# Route changes require a fresh silence lag frame for the new channel mode.
s = replace_once(s,
'''                    if (reinit_err == OPUS_OK) {
                        encoder_channels = target_channels;
                        encoder_params_dirty = true; /* force re-apply below */''',
'''                    if (reinit_err == OPUS_OK) {
                        encoder_channels = target_channels;
                        encoder_params_dirty = true; /* force re-apply below */
                        speaker_pipeline_primed = false;''',
"route reinit pipeline reset")

# Keep prediction disabled in both dynamic tuning branches and update comment.
s = s.replace(' * - Otherwise            → full quality (160k, pred on, full BW)',
              ' * - Otherwise            → low-latency quality (160k, pred off, full BW)')

# Batch route mismatch invalidates the lag frame.
s = replace_once(s,
'''                    audio_batch_count = 0;
                }
                if (audio_batch_count == 0) {''',
'''                    audio_batch_count = 0;
                    speaker_pipeline_primed = false;
                }
                if (!speaker_on)
                    speaker_pipeline_primed = false;
                if (speaker_on && !speaker_pipeline_primed)
                    prime_speaker_pipeline(target_channels);
                if (audio_batch_count == 0) {''',
"batch pipeline priming")

old_producer = '''                /* Optional speaker producer. Frame 0 is encoded roughly one USB
                 * producer period earlier than with the old 1024-sample batch. */
                if (speaker_on) {
#if LOG_LEVEL >= 3
                    uint64_t t_res0 = bflb_mtimer_get_time_us();
#endif
                    deinterleave_4ch(slot_pcm, ACCUM_SAMPLES);
                    int mono = (encoder_channels == 1);
                    resample_512_480(slot_pcm, spk_resamp, mono);
#if LOG_LEVEL >= 3
                    prof_resamp += bflb_mtimer_get_time_us() - t_res0;
#endif

                    encode_start_us = bflb_mtimer_get_time_us();
                    encoding_in_progress = true;
                    int encoded = opus_encode(encoder, spk_resamp, OPUS_FRAME_SAMPLES,
                                              opus_slots[slot], OPUS_OUT_SIZE);
                    encoding_in_progress = false;
#if LOG_LEVEL >= 3
                    prof_opus += bflb_mtimer_get_time_us() - encode_start_us;
#endif
                    if (encoder_reset_pending) {
                        encoder_reset_pending = false;
                        opus_encoder_ctl(encoder, OPUS_RESET_STATE);
                    }
                    if (encoded <= 0) {
                        LOG_ERR("[AUDIO] Opus encode error: %d\\n", encoded);
                        memset(opus_slots[slot], 0, OPUS_OUT_SIZE);
                    } else if (encoded < OPUS_OUT_SIZE) {
                        int pad_ret = opus_packet_pad(opus_slots[slot], encoded, OPUS_OUT_SIZE);
                        if (pad_ret != OPUS_OK)
                            memset(opus_slots[slot] + encoded, 0, OPUS_OUT_SIZE - encoded);
                    }
                } else {
                    memset(opus_slots[slot], 0, OPUS_OUT_SIZE);
                }

                audio_batch_count++;'''
new_producer = '''                /* BL616 single-core haptics-first scheduler.
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

                audio_batch_count++;'''
s = replace_once(s, old_producer, new_producer, "haptics-first speaker producer")

# After the current haptics packet has been submitted, encode the second
# speaker frame into the lag slot. Place this after profiling so send timing
# does not include the intentionally deferred Opus work.
post_anchor = '''#endif
            audio_frame_done:
                ;'''
post_new = '''#endif
                if (speaker_on) {
                    /* Current haptics are already in the Bluetooth stack. */
                    encode_speaker_frame(slot_pcm, opus_slots[0]);
                    speaker_pipeline_primed = true;
                }
            audio_frame_done:
                ;'''
s = replace_once(s, post_anchor, post_new, "deferred second speaker encode")

# Reset helpers invalidate the speaker lag frame.
reset_pat = '''    memset(opus_slots, 0, sizeof(opus_slots));
    memset(haptic_slots, 0, sizeof(haptic_slots));
    audio_batch_count = 0;'''
if s.count(reset_pat) != 2:
    raise SystemExit(f"reset pattern expected 2 matches, found {s.count(reset_pat)}")
s = s.replace(reset_pat,
'''    memset(opus_slots, 0, sizeof(opus_slots));
    memset(haptic_slots, 0, sizeof(haptic_slots));
    audio_batch_count = 0;
    speaker_pipeline_primed = false;''')

p.write_text(s)
print("BL616 haptics-first scheduler patch applied")
