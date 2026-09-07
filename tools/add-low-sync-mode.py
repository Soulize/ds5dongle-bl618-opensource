from pathlib import Path


def replace_once(path, old, new):
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one match, got {count}")
    p.write_text(text.replace(old, new, 1))


replace_once(
    "src/config.h",
    """/* Audio/haptics scheduler policy for the single-core BL616.\n * BALANCED_1F is the current low-latency implementation.\n * LEGACY_SYNC keeps speaker and haptics time-aligned and waits for both\n * current Opus frames before submitting 0x39.\n * MAX_HAPTICS_2F submits haptics before any current-batch Opus work and\n * therefore keeps speaker one whole 0x39 batch (~21.33 ms) behind. */\nenum haptic_latency_mode {\n    HAPTIC_LATENCY_BALANCED_1F = 0,\n    HAPTIC_LATENCY_LEGACY_SYNC = 1,\n    HAPTIC_LATENCY_MAX_2F      = 2,\n};\n""",
    """/* Audio/haptics scheduler policy for the single-core BL616.\n * BALANCED_1F prioritizes haptics by keeping speaker one 512-sample frame behind.\n * LEGACY_SYNC keeps speaker/haptics aligned but defers both current Opus encodes.\n * MAX_HAPTICS_2F keeps speaker a full 0x39 batch behind.\n * LOW_SYNC keeps speaker/haptics aligned while pre-encoding frame 0 during the\n * first 10.67 ms window, leaving only frame-1 Opus on the haptics critical path. */\nenum haptic_latency_mode {\n    HAPTIC_LATENCY_BALANCED_1F = 0,\n    HAPTIC_LATENCY_LEGACY_SYNC = 1,\n    HAPTIC_LATENCY_MAX_2F      = 2,\n    HAPTIC_LATENCY_LOW_SYNC    = 3,\n};\n""",
)

replace_once(
    "src/config.c",
    """    if (b->haptic_latency_mode > HAPTIC_LATENCY_MAX_2F)\n        b->haptic_latency_mode = HAPTIC_LATENCY_BALANCED_1F;\n""",
    """    if (b->haptic_latency_mode > HAPTIC_LATENCY_LOW_SYNC)\n        b->haptic_latency_mode = HAPTIC_LATENCY_BALANCED_1F;\n""",
)

replace_once(
    "src/audio.c",
    """                if (!speaker_on || latency_mode == HAPTIC_LATENCY_LEGACY_SYNC) {\n                    speaker_pipeline_primed = false;\n                } else if (!speaker_pipeline_primed) {\n                    prime_speaker_pipeline(target_channels);\n                }\n""",
    """                if (!speaker_on ||\n                    latency_mode == HAPTIC_LATENCY_LEGACY_SYNC ||\n                    latency_mode == HAPTIC_LATENCY_LOW_SYNC) {\n                    /* Synchronized modes always send the two current Opus\n                     * frames, so they never need lag-pipeline silence priming. */\n                    speaker_pipeline_primed = false;\n                } else if (!speaker_pipeline_primed) {\n                    prime_speaker_pipeline(target_channels);\n                }\n""",
)

replace_once(
    "src/audio.c",
    """                if (speaker_on && slot == 0) {\n                    if (latency_mode == HAPTIC_LATENCY_BALANCED_1F) {\n                        /* Current low-latency policy: encode frame 0 during the\n                         * first 10.67ms window. At send time speaker contains\n                         * [previous frame1, current frame0]. */\n#if LOG_LEVEL >= 3\n                        uint64_t t_op0 = bflb_mtimer_get_time_us();\n#endif\n                        encode_speaker_frame(slot_pcm, opus_slots[1]);\n#if LOG_LEVEL >= 3\n                        prof_opus += bflb_mtimer_get_time_us() - t_op0;\n#endif\n                    } else {\n                        /* Legacy-sync and max-2f intentionally defer frame 0\n                         * encoding; retain PCM after zero-copy USB release. */\n                        memcpy(speaker_frame0_stage, slot_pcm,\n                               sizeof(speaker_frame0_stage));\n                    }\n                }\n""",
    """                if (speaker_on && slot == 0) {\n                    if (latency_mode == HAPTIC_LATENCY_BALANCED_1F) {\n                        /* Haptics-first one-frame lag: encode current frame 0\n                         * during the first 10.67ms window. The outgoing pair is\n                         * [previous frame1, current frame0]. */\n#if LOG_LEVEL >= 3\n                        uint64_t t_op0 = bflb_mtimer_get_time_us();\n#endif\n                        encode_speaker_frame(slot_pcm, opus_slots[1]);\n#if LOG_LEVEL >= 3\n                        prof_opus += bflb_mtimer_get_time_us() - t_op0;\n#endif\n                    } else if (latency_mode == HAPTIC_LATENCY_LOW_SYNC) {\n                        /* Synchronized low-latency mode: pre-encode current\n                         * frame 0 now. Frame 1 will be the only Opus encode on\n                         * the second-frame/haptics critical path. */\n#if LOG_LEVEL >= 3\n                        uint64_t t_op0 = bflb_mtimer_get_time_us();\n#endif\n                        encode_speaker_frame(slot_pcm, opus_slots[0]);\n#if LOG_LEVEL >= 3\n                        prof_opus += bflb_mtimer_get_time_us() - t_op0;\n#endif\n                    } else {\n                        /* Legacy-sync and max-2f intentionally defer frame 0\n                         * encoding; retain PCM after zero-copy USB release. */\n                        memcpy(speaker_frame0_stage, slot_pcm,\n                               sizeof(speaker_frame0_stage));\n                    }\n                }\n""",
)

replace_once(
    "src/audio.c",
    """                if (speaker_on && latency_mode == HAPTIC_LATENCY_LEGACY_SYNC) {\n                    /* Original-style synchronized policy: both current speaker\n                     * frames are encoded only after the haptics pair is ready.\n                     * This keeps speaker/haptics aligned but puts both Opus\n                     * encodes on the haptics critical path. */\n#if LOG_LEVEL >= 3\n                    uint64_t t_op_legacy = bflb_mtimer_get_time_us();\n#endif\n                    encode_speaker_frame(speaker_frame0_stage, opus_slots[0]);\n                    encode_speaker_frame(slot_pcm, opus_slots[1]);\n#if LOG_LEVEL >= 3\n                    prof_opus += bflb_mtimer_get_time_us() - t_op_legacy;\n#endif\n                }\n""",
    """                if (speaker_on && latency_mode == HAPTIC_LATENCY_LEGACY_SYNC) {\n                    /* Original-style synchronized policy: both current speaker\n                     * frames are encoded only after the haptics pair is ready.\n                     * This keeps speaker/haptics aligned but puts both Opus\n                     * encodes on the haptics critical path. */\n#if LOG_LEVEL >= 3\n                    uint64_t t_op_legacy = bflb_mtimer_get_time_us();\n#endif\n                    encode_speaker_frame(speaker_frame0_stage, opus_slots[0]);\n                    encode_speaker_frame(slot_pcm, opus_slots[1]);\n#if LOG_LEVEL >= 3\n                    prof_opus += bflb_mtimer_get_time_us() - t_op_legacy;\n#endif\n                } else if (speaker_on && latency_mode == HAPTIC_LATENCY_LOW_SYNC) {\n                    /* Frame 0 was encoded during the first 10.67ms window.\n                     * Encode only the just-arrived frame 1, then submit the\n                     * aligned current haptics + current speaker pair. */\n#if LOG_LEVEL >= 3\n                    uint64_t t_op_low_sync = bflb_mtimer_get_time_us();\n#endif\n                    encode_speaker_frame(slot_pcm, opus_slots[1]);\n#if LOG_LEVEL >= 3\n                    prof_opus += bflb_mtimer_get_time_us() - t_op_low_sync;\n#endif\n                }\n""",
)

replace_once(
    "LATENCY_MODES.md",
    """| 2 | `HAPTIC_LATENCY_MAX_2F` | Speaker lags by one complete two-frame 0x39 batch (~21.33 ms). | The current haptics pair is submitted before either current-batch Opus encode; both speaker frames are encoded afterward for the next packet. |\n""",
    """| 2 | `HAPTIC_LATENCY_MAX_2F` | Speaker lags by one complete two-frame 0x39 batch (~21.33 ms). | The current haptics pair is submitted before either current-batch Opus encode; both speaker frames are encoded afterward for the next packet. |\n| 3 | `HAPTIC_LATENCY_LOW_SYNC` | Speaker and haptics stay time-aligned, with no intentional 10.67 ms speaker lag. | Frame-0 Opus is pre-encoded during the first 10.67 ms window; after frame 1 arrives, only one current Opus encode remains before 0x39 submission. Haptics therefore pays actual frame-1 encode time rather than a fixed one-frame speaker offset. |\n""",
)

print("low-sync mode transform applied")
