/* E907 P-extension optimized SILK SigProc macros.
 *
 * sclip32 rd, rs1, imm5 : rd = clamp(rs1, -2^imm, 2^imm - 1)
 */

#ifndef SILK_SIGPROC_FIX_E907_H
#define SILK_SIGPROC_FIX_E907_H

#undef silk_SAT16
static OPUS_INLINE opus_int16 silk_SAT16_e907(opus_int32 a)
{
    opus_int32 res;
    __asm__ volatile("sclip32 %0, %1, 15"
                     : "=r"(res)
                     : "r"(a));
    return (opus_int16)res;
}
#define silk_SAT16(a) (silk_SAT16_e907(a))

#endif /* SILK_SIGPROC_FIX_E907_H */
