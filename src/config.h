#ifndef CONFIG_H
#define CONFIG_H

#include <stdint.h>
#include <stdbool.h>

/* Input delivery policy. Zero intentionally preserves the existing
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
struct __attribute__((packed)) config_body {
    uint8_t config_version;
    float   haptics_gain;         /* [1.0,2.0]  — haptics amplitude scaling */
    uint8_t speaker_volume;       /* [0,127]    — speaker volume level */
    uint8_t headset_vol_offset;   /* [0,127]    — headset volume reduction from speaker */
    uint8_t speaker_gain;         /* [0,7]      — speaker gain (SpeakerCompPreGain) */
    uint8_t inactive_time;        /* [0,60] min  (0 = disable) */
    uint8_t disable_led;          /* bool */
    uint8_t polling_rate_mode;    /* 0: 250Hz, 1: 500Hz, 2: real-time */
    uint8_t audio_buffer_length;  /* [16,127]   — controller audio buffer depth */
    uint8_t controller_mode;      /* 0: DS5, 1: DSE, 2: Auto */
    uint8_t enable_usb_sn;        /* bool */
    uint8_t ps_shortcut_enabled;  /* bool */
    uint8_t disable_mic;          /* bool       — disable mic passthrough */
    uint8_t disable_speaker;      /* bool       — disable Opus speaker encoding */
    uint8_t enable_wake;          /* bool */
    uint8_t trigger_reduce;       /* [0,10]     — trigger motor power reduction */
    uint8_t lock_volume;          /* 0=off, 1=block audio routing, 2=lock volume, 3=full lock */
    uint8_t dse_detected;         /* bool — Auto mode remembers last detection */
    uint8_t usb_stealth;          /* bool — hide USB until BT controller connects */
    uint8_t led_r;                /* [0-255] custom LED red   (0xFF = default white) */
    uint8_t led_g;                /* [0-255] custom LED green (0xFF = default white) */
    uint8_t led_b;                /* [0-255] custom LED blue  (0xFF = default white) */
    uint8_t tp_mode;              /* 0=off, 1=dpad, 2=Lmouse+Rdpad, 3=Ldpad+Rmouse, 4=split */
    uint8_t tp_mode_enabled_mask; /* bitmask of enabled modes (bit0-bit4) */
    uint8_t tp_mouse_sensitivity; /* [1-32], default 8 */
    uint8_t audio_haptic;         /* 0=off, 1=auto(game priority), 2=force */
    uint8_t tp_click_mode;        /* 0=touch triggers dirs, 1=click required */
    uint8_t battery_led;          /* bool — show battery level on player LEDs */
    uint8_t input_report_mode;    /* enum input_report_mode */
    uint8_t haptic_latency_mode;  /* enum haptic_latency_mode */
};

#define CONFIG_VERSION  4

void config_load(void);
bool config_save(void);
void config_validate(void);

struct config_body *config_get(void);
void config_set(const uint8_t *data, uint16_t len);

/* Convenience accessors for hot-path fields */
static inline bool config_wake_enabled(void)       { return config_get()->enable_wake; }
static inline bool config_led_disabled(void)        { return config_get()->disable_led; }
static inline uint8_t config_inactive_minutes(void) { return config_get()->inactive_time; }
static inline uint8_t config_polling_mode(void)     { return config_get()->polling_rate_mode; }
static inline bool config_ps_shortcut(void)         { return config_get()->ps_shortcut_enabled; }
static inline uint8_t config_controller_mode(void)  { return config_get()->controller_mode; }
static inline bool config_dse_detected(void)        { return config_get()->dse_detected; }
static inline bool config_speaker_disabled(void)    { return config_get()->disable_speaker; }
static inline bool config_mic_disabled(void)         { return config_get()->disable_mic; }
static inline uint8_t config_audio_buf_len(void)    { return config_get()->audio_buffer_length; }
static inline uint8_t config_input_report_mode(void) { return config_get()->input_report_mode; }
static inline uint8_t config_haptic_latency_mode(void) { return config_get()->haptic_latency_mode; }
static inline bool config_usb_stealth(void)         { return config_get()->usb_stealth; }
static inline uint8_t config_apply_hp_offset(uint8_t base)
{
    uint8_t off = config_get()->headset_vol_offset;
    return (base > off) ? base - off : 0;
}

#endif /* CONFIG_H */
