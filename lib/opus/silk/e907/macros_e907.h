/* E907 P-extension optimized SILK macros.
 *
 * smmwb rd, rs1, rs2 : rd = (rs1 * sign_ext(rs2[15:0])) >> 16
 * smmwt rd, rs1, rs2 : rd = (rs1 * sign_ext(rs2[31:16])) >> 16
 *
 * Reference: Xtensa LX7 uses mulsh for the same operations;
 * E907's smmwb/smmwt are single-cycle and more direct.
 */

#ifndef SILK_MACROS_E907_H
#define SILK_MACROS_E907_H

/* (a32 * (opus_int32)((opus_int16)(b32))) >> 16 */
#undef silk_SMULWB
static OPUS_INLINE opus_int32 silk_SMULWB_e907(opus_int32 a32, opus_int32 b32)
{
    opus_int32 res;
    __asm__ volatile("smmwb %0, %1, %2"
                     : "=r"(res)
                     : "r"(a32), "r"(b32));
    return res;
}
#define silk_SMULWB(a32, b32) (silk_SMULWB_e907(a32, b32))

/* a32 + (b32 * (opus_int32)((opus_int16)(c32))) >> 16 */
#undef silk_SMLAWB
#define silk_SMLAWB(a32, b32, c32) ((a32) + silk_SMULWB_e907(b32, c32))

/* (a32 * (b32 >> 16)) >> 16 */
#undef silk_SMULWT
static OPUS_INLINE opus_int32 silk_SMULWT_e907(opus_int32 a32, opus_int32 b32)
{
    opus_int32 res;
    __asm__ volatile("smmwt %0, %1, %2"
                     : "=r"(res)
                     : "r"(a32), "r"(b32));
    return res;
}
#define silk_SMULWT(a32, b32) (silk_SMULWT_e907(a32, b32))

/* a32 + (b32 * (c32 >> 16)) >> 16 */
#undef silk_SMLAWT
#define silk_SMLAWT(a32, b32, c32) ((a32) + silk_SMULWT_e907(b32, c32))

#endif /* SILK_MACROS_E907_H */
