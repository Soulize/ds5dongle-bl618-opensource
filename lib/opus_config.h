#ifndef OPUS_CONFIG_H
#define OPUS_CONFIG_H

#define FIXED_POINT        1
#define DISABLE_FLOAT_API  1
#define OPUS_BUILD         1
#define VAR_ARRAYS         1

#define PACKAGE_VERSION    "1.5.2-bl616"

#define HAVE_LRINTF        1

/* E907 vendor DSP — ff1 (CLZ) disabled: causes opus_encode hang
 * (self-test passes but fails under ISR/pipeline pressure).
 * All other DSP instructions enabled.
 * TCM placement kept for cache-miss reduction. */
#if defined(__riscv)
#define E907_OPUS_DSP      1
#define E907_DISABLE_FF1   1
#define OPUS_TCM_CODE      __attribute__((section(".tcm_code")))
#define OPUS_TCM_CONST     __attribute__((section(".tcm_const")))
#else
#define OPUS_TCM_CODE
#define OPUS_TCM_CONST
#endif

/* Intra-encode profiling: only active at LOG_LEVEL >= 3 (debug builds). */
#ifndef LOG_LEVEL
#define LOG_LEVEL 2
#endif
#if LOG_LEVEL >= 3
#define OPUS_ENCODE_PROFILING 1
#endif
#ifdef OPUS_ENCODE_PROFILING
extern volatile unsigned int opus_prof_ts[16];
static inline unsigned int _opus_prof_rd(void) {
    unsigned int v;
    __asm__ volatile("csrr %0, mcycle" : "=r"(v));
    return v;
}
#define OPUS_PROF(idx) (opus_prof_ts[idx] = _opus_prof_rd())
#else
#define OPUS_PROF(idx)
#endif

#include <stdlib.h>
#include <string.h>

#endif
