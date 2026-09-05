/* Copyright (C) 2007-2009 Xiph.Org Foundation
   Copyright (C) 2003-2008 Jean-Marc Valin
   Copyright (C) 2007-2008 CSIRO */
/**
   @file fixed_generic.h
   @brief Generic fixed-point operations
*/
/*
   Redistribution and use in source and binary forms, with or without
   modification, are permitted provided that the following conditions
   are met:

   - Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.

   - Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in the
   documentation and/or other materials provided with the distribution.

   THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
   ``AS IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
   LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
   A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER
   OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
   EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
   PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
   PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
   LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
   NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
   SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
*/

#ifndef FIXED_GENERIC_H
#define FIXED_GENERIC_H

/** Multiply a 16-bit signed value by a 16-bit unsigned value. The result is a 32-bit signed value */
#define MULT16_16SU(a,b) ((opus_val32)(opus_val16)(a)*(opus_val32)(opus_uint16)(b))

/** 16x32 multiplication, followed by a 16-bit shift right. Results fits in 32 bits */
#if defined(E907_OPUS_DSP)
static OPUS_INLINE opus_val32 e907_mult16_32_q16(opus_val16 a, opus_val32 b)
{
    opus_val32 result;
    __asm__ volatile("smmwb %0, %1, %2"
                     : "=r"(result)
                     : "r"(b), "r"((opus_val32)a));
    return result;
}
#define MULT16_32_Q16(a,b) e907_mult16_32_q16((opus_val16)(a),(opus_val32)(b))
#elif OPUS_FAST_INT64
#define MULT16_32_Q16(a,b) ((opus_val32)SHR((opus_int64)((opus_val16)(a))*(b),16))
#else
#define MULT16_32_Q16(a,b) ADD32(MULT16_16((a),SHR((b),16)), SHR(MULT16_16SU((a),((b)&0x0000ffff)),16))
#endif

/** 16x32 multiplication, followed by a 16-bit shift right (round-to-nearest). Results fits in 32 bits */
#if OPUS_FAST_INT64
#define MULT16_32_P16(a,b) ((opus_val32)PSHR((opus_int64)((opus_val16)(a))*(b),16))
#else
#define MULT16_32_P16(a,b) ADD32(MULT16_16((a),SHR((b),16)), PSHR(MULT16_16SU((a),((b)&0x0000ffff)),16))
#endif

/** 16x32 multiplication, followed by a 15-bit shift right. Results fits in 32 bits */
#if defined(E907_OPUS_DSP)
static OPUS_INLINE opus_val32 e907_mult16_32_q15(opus_val16 a, opus_val32 b)
{
    opus_val32 result;
    __asm__ volatile("kmmwb2 %0, %1, %2"
                     : "=r"(result)
                     : "r"(b), "r"((opus_val32)a));
    return result;
}
#define MULT16_32_Q15(a,b) e907_mult16_32_q15((opus_val16)(a),(opus_val32)(b))
#elif OPUS_FAST_INT64
#define MULT16_32_Q15(a,b) ((opus_val32)SHR((opus_int64)((opus_val16)(a))*(b),15))
#else
#define MULT16_32_Q15(a,b) ADD32(SHL(MULT16_16((a),SHR((b),16)),1), SHR(MULT16_16SU((a),((b)&0x0000ffff)),15))
#endif

/** 32x32 multiplication, followed by a 16-bit shift right. Results fits in 32 bits */
#if defined(E907_OPUS_DSP)
static OPUS_INLINE opus_val32 e907_mult32_32_q16(opus_val32 a, opus_val32 b)
{
    opus_int64 product;
    __asm__ volatile("mulsr64 %0, %1, %2"
                     : "=r"(product)
                     : "r"(a), "r"(b));
    return (opus_val32)(product >> 16);
}
#define MULT32_32_Q16(a,b) e907_mult32_32_q16((opus_val32)(a),(opus_val32)(b))
#elif OPUS_FAST_INT64
#define MULT32_32_Q16(a,b) ((opus_val32)SHR((opus_int64)(a)*(opus_int64)(b),16))
#else
#define MULT32_32_Q16(a,b) (ADD32(ADD32(ADD32((opus_val32)(SHR32(((opus_uint32)((a)&0x0000ffff)*(opus_uint32)((b)&0x0000ffff)),16)), MULT16_16SU(SHR32(a,16),((b)&0x0000ffff))), MULT16_16SU(SHR32(b,16),((a)&0x0000ffff))), SHL32(MULT16_16(SHR32(a,16),SHR32(b,16)),16)))
#endif

/** 32x32 multiplication, followed by a 31-bit shift right. Results fits in 32 bits */
#if defined(E907_OPUS_DSP)
static OPUS_INLINE opus_val32 e907_mult32_32_q31(opus_val32 a, opus_val32 b)
{
    opus_val32 result;
    __asm__ volatile("kwmmul %0, %1, %2"
                     : "=r"(result)
                     : "r"(a), "r"(b));
    return result;
}
#define MULT32_32_Q31(a,b) e907_mult32_32_q31((opus_val32)(a),(opus_val32)(b))
#elif OPUS_FAST_INT64
#define MULT32_32_Q31(a,b) ((opus_val32)SHR((opus_int64)(a)*(opus_int64)(b),31))
#else
#define MULT32_32_Q31(a,b) ADD32(ADD32(SHL(MULT16_16(SHR((a),16),SHR((b),16)),1), SHR(MULT16_16SU(SHR((a),16),((b)&0x0000ffff)),15)), SHR(MULT16_16SU(SHR((b),16),((a)&0x0000ffff)),15))
#endif

/** 32x32 multiplication, followed by a 31-bit shift right (with rounding). Results fits in 32 bits */
#if defined(E907_OPUS_DSP)
static OPUS_INLINE opus_val32 e907_mult32_32_p31(opus_val32 a, opus_val32 b)
{
    opus_val32 result;
    __asm__ volatile("kwmmul.u %0, %1, %2"
                     : "=r"(result)
                     : "r"(a), "r"(b));
    return result;
}
#define MULT32_32_P31(a,b) e907_mult32_32_p31((opus_val32)(a),(opus_val32)(b))
#define MULT32_32_P31_ovflw(a,b) MULT32_32_P31((a),(b))
#elif OPUS_FAST_INT64
#define MULT32_32_P31(a,b) ((opus_val32)SHR(1073741824+(opus_int64)(a)*(opus_int64)(b),31))
#define MULT32_32_P31_ovflw(a,b) MULT32_32_P31(a,b)
#else
#define MULT16_16U(a,b) ((opus_uint32)(a)*(opus_uint32)(b))
#define MULT32_32_P31(a,b) ADD32(SHL(MULT16_16(SHR((a),16),SHR((b),16)),1), SHR32(128+(opus_int32)SHR(MULT16_16U(((a)&0x0000ffff),((b)&0x0000ffff)),16+7) + SHR32(MULT16_16SU(SHR((a),16),((b)&0x0000ffff)),7) + SHR32(MULT16_16SU(SHR((b),16),((a)&0x0000ffff)),7), 8) )
#define MULT32_32_P31_ovflw(a,b) ADD32_ovflw(SHL(MULT16_16(SHR((a),16),SHR((b),16)),1), SHR32(128+(opus_int32)SHR(MULT16_16U(((a)&0x0000ffff),((b)&0x0000ffff)),16+7) + SHR32(MULT16_16SU(SHR((a),16),((b)&0x0000ffff)),7) + SHR32(MULT16_16SU(SHR((b),16),((a)&0x0000ffff)),7), 8) )
#endif

/** 32x32 multiplication, followed by a 32-bit shift right. Results fits in 32 bits */
#if defined(E907_OPUS_DSP)
static OPUS_INLINE opus_val32 e907_mult32_32_q32(opus_val32 a, opus_val32 b)
{
    opus_val32 result;
    __asm__ volatile("mulh %0, %1, %2"
                     : "=r"(result)
                     : "r"(a), "r"(b));
    return result;
}
#define MULT32_32_Q32(a,b) e907_mult32_32_q32((opus_val32)(a),(opus_val32)(b))
#elif OPUS_FAST_INT64
#define MULT32_32_Q32(a,b) ((opus_val32)SHR((opus_int64)(a)*(opus_int64)(b),32))
#else
#define MULT32_32_Q32(a,b) ADD32(ADD32(MULT16_16(SHR((a),16),SHR((b),16)), SHR(MULT16_16SU(SHR((a),16),((b)&0x0000ffff)),16)), SHR(MULT16_16SU(SHR((b),16),((a)&0x0000ffff)),16))
#endif

/** Compile-time conversion of float constant to 16-bit value */
#define QCONST16(x,bits) ((opus_val16)(.5+(x)*(((opus_val32)1)<<(bits))))

/** Compile-time conversion of float constant to 32-bit value */
#define QCONST32(x,bits) ((opus_val32)(.5+(x)*(((opus_int64)1)<<(bits))))

/** Compile-time conversion of float constant to log gain value */
#define GCONST2(x,bits) ((celt_glog)(.5+(x)*(((celt_glog)1)<<(bits))))

/** Compile-time conversion of float constant to DB_SHIFT log gain value */
#define GCONST(x) GCONST2((x),DB_SHIFT)

/** Negate a 16-bit value */
#define NEG16(x) (-(x))
/** Negate a 32-bit value */
#define NEG32(x) (-(x))

/** Change a 32-bit value into a 16-bit value. The value is assumed to fit in 16-bit, otherwise the result is undefined */
#define EXTRACT16(x) ((opus_val16)(x))
/** Change a 16-bit value into a 32-bit value */
#define EXTEND32(x) ((opus_val32)(x))

/** Arithmetic shift-right of a 16-bit value */
#define SHR16(a,shift) ((a) >> (shift))
/** Arithmetic shift-left of a 16-bit value */
#define SHL16(a,shift) ((opus_int16)((opus_uint16)(a)<<(shift)))
/** Arithmetic shift-right of a 32-bit value */
#define SHR32(a,shift) ((a) >> (shift))
/** Arithmetic shift-left of a 32-bit value */
#define SHL32(a,shift) ((opus_int32)((opus_uint32)(a)<<(shift)))

/** 32-bit arithmetic shift right with rounding-to-nearest instead of rounding down */
#define PSHR32(a,shift) (SHR32((a)+((EXTEND32(1)<<((shift))>>1)),shift))
/** 32-bit arithmetic shift right where the argument can be negative */
#define VSHR32(a, shift) (((shift)>0) ? SHR32(a, shift) : SHL32(a, -(shift)))

/** Arithmetic shift-right of a 64-bit value */
#define SHR64(a,shift) ((a) >> (shift))

/** "RAW" macros, should not be used outside of this header file */
#define SHR(a,shift) ((a) >> (shift))
#define SHL(a,shift) SHL32(a,shift)
#define PSHR(a,shift) (SHR((a)+((EXTEND32(1)<<((shift))>>1)),shift))
#define SATURATE(x,a) (((x)>(a) ? (a) : (x)<-(a) ? -(a) : (x)))

#define SATURATE16(x) (EXTRACT16((x)>32767 ? 32767 : (x)<-32768 ? -32768 : (x)))

/** Shift by a and round-to-nearest 32-bit value. Result is a 16-bit value */
#define ROUND16(x,a) (EXTRACT16(PSHR32((x),(a))))
/** Shift by a and round-to-nearest 32-bit value. Result is a saturated 16-bit value */
#define SROUND16(x,a) EXTRACT16(SATURATE(PSHR32(x,a), 32767));

/** Divide by two */
#define HALF16(x)  (SHR16(x,1))
#define HALF32(x)  (SHR32(x,1))

/** Add two 16-bit values */
#define ADD16(a,b) ((opus_val16)((opus_val16)(a)+(opus_val16)(b)))
/** Subtract two 16-bit values */
#define SUB16(a,b) ((opus_val16)(a)-(opus_val16)(b))
/** Add two 32-bit values */
#define ADD32(a,b) ((opus_val32)(a)+(opus_val32)(b))
/** Subtract two 32-bit values */
#define SUB32(a,b) ((opus_val32)(a)-(opus_val32)(b))

/** Add two 32-bit values, ignore any overflows */
#define ADD32_ovflw(a,b) ((opus_val32)((opus_uint32)(a)+(opus_uint32)(b)))
/** Subtract two 32-bit values, ignore any overflows */
#define SUB32_ovflw(a,b) ((opus_val32)((opus_uint32)(a)-(opus_uint32)(b)))
/* Avoid MSVC warning C4146: unary minus operator applied to unsigned type */
/** Negate 32-bit value, ignore any overflows */
#define NEG32_ovflw(a) ((opus_val32)(0-(opus_uint32)(a)))
/** 32-bit shift left, ignoring overflows */
#define SHL32_ovflw(a,shift) SHL32(a,shift)
/** 32-bit arithmetic shift right with rounding-to-nearest, ignoring overflows */
#define PSHR32_ovflw(a,shift) (SHR32(ADD32_ovflw(a, (EXTEND32(1)<<(shift)>>1)),shift))

/** 16x16 multiplication where the result fits in 16 bits */
#define MULT16_16_16(a,b)     ((((opus_val16)(a))*((opus_val16)(b))))

/** 32x32 multiplication where the result fits in 32 bits */
#define MULT32_32_32(a,b)     ((((opus_val32)(a))*((opus_val32)(b))))

/* (opus_val32)(opus_val16) gives TI compiler a hint that it's 16x16->32 multiply */
/** 16x16 multiplication where the result fits in 32 bits */
#define MULT16_16(a,b)     (((opus_val32)(opus_val16)(a))*((opus_val32)(opus_val16)(b)))

/** 16x16 multiply-add where the result fits in 32 bits */
#define MAC16_16(c,a,b) (ADD32((c),MULT16_16((a),(b))))
/** 16x32 multiply, followed by a 15-bit shift right and 32-bit add.
    b must fit in 31 bits.
    Result fits in 32 bits. */
#define MAC16_32_Q15(c,a,b) ADD32((c),ADD32(MULT16_16((a),SHR((b),15)), SHR(MULT16_16((a),((b)&0x00007fff)),15)))

/** 16x32 multiplication, followed by a 16-bit shift right and 32-bit add.
    Results fits in 32 bits */
#define MAC16_32_Q16(c,a,b) ADD32((c),ADD32(MULT16_16((a),SHR((b),16)), SHR(MULT16_16SU((a),((b)&0x0000ffff)),16)))

#define MULT16_16_Q11_32(a,b) (SHR(MULT16_16((a),(b)),11))
#define MULT16_16_Q11(a,b) (SHR(MULT16_16((a),(b)),11))
#define MULT16_16_Q13(a,b) (SHR(MULT16_16((a),(b)),13))
#define MULT16_16_Q14(a,b) (SHR(MULT16_16((a),(b)),14))
#define MULT16_16_Q15(a,b) (SHR(MULT16_16((a),(b)),15))

#define MULT16_16_P13(a,b) (SHR(ADD32(4096,MULT16_16((a),(b))),13))
#define MULT16_16_P14(a,b) (SHR(ADD32(8192,MULT16_16((a),(b))),14))
#define MULT16_16_P15(a,b) (SHR(ADD32(16384,MULT16_16((a),(b))),15))

/** Divide a 32-bit value by a 16-bit value. Result fits in 16 bits */
#define DIV32_16(a,b) ((opus_val16)(((opus_val32)(a))/((opus_val16)(b))))

/** Divide a 32-bit value by a 32-bit value. Result fits in 32 bits */
#define DIV32(a,b) (((opus_val32)(a))/((opus_val32)(b)))

#if defined(__mips)
#include "mips/fixed_generic_mipsr1.h"
#endif

/* ── E907 P-extension: low-level primitive overrides ──
 * Reference: Nuclei fixed_riscv.h (nuclei-audio-library)
 * These replace high-frequency generic macros with single P-ext instructions.
 * Verified on riscv64-unknown-elf-gcc 10.2, -march=rv32imafcpzpsfoperand_xtheade.
 */
#if defined(E907_OPUS_DSP)

/* PSHR32: rounding arithmetic right shift.
 * Generic: (a + (1 << (shift-1))) >> shift  = 4 instructions (li+addi+add+srai)
 * E907:    sra.u                             = 1 instruction                    */
#undef PSHR32
static OPUS_INLINE opus_val32 e907_pshr32(opus_val32 a, int shift)
{
    opus_val32 res;
    __asm__ volatile("sra.u %0, %1, %2" : "=r"(res) : "r"(a), "r"(shift));
    return res;
}
#define PSHR32(a,shift) e907_pshr32((opus_val32)(a),(int)(shift))

#undef PSHR
#define PSHR(a,shift) e907_pshr32((opus_val32)(a),(int)(shift))

#undef PSHR32_ovflw
#define PSHR32_ovflw(a,shift) e907_pshr32((opus_val32)(a),(int)(shift))

/* VSHR32: variable-direction shift (right if shift>0, left if shift<0).
 * Generic: if-else + shift = 3-4 instructions + branch
 * E907:    neg + kslraw     = 2 instructions, no branch                */
#undef VSHR32
static OPUS_INLINE opus_val32 e907_vshr32(opus_val32 a, int shift)
{
    opus_val32 res;
    int neg_shift = -shift;
    __asm__ volatile("kslraw %0, %1, %2" : "=r"(res) : "r"(a), "r"(neg_shift));
    return res;
}
#define VSHR32(a,shift) e907_vshr32((opus_val32)(a),(int)(shift))

/* SATURATE16: clamp to [-32768, 32767].
 * Generic: dual-branch compare = 8-10 instructions
 * E907:    sclip32 imm=15     = 1 instruction           */
#undef SATURATE16
static OPUS_INLINE opus_val16 e907_saturate16(opus_val32 x)
{
    opus_val32 res;
    __asm__ volatile("sclip32 %0, %1, 15" : "=r"(res) : "r"(x));
    return (opus_val16)res;
}
#define SATURATE16(x) e907_saturate16((opus_val32)(x))

/* SROUND16: rounding shift + saturate to int16.
 * Generic: PSHR32 + SATURATE = 11-13 instructions + branch
 * E907:    sra.u  + sclip32  = 2 instructions, no branch  */
#undef SROUND16
static OPUS_INLINE opus_val16 e907_sround16(opus_val32 x, int a)
{
    opus_val32 shifted = e907_pshr32(x, a);
    return e907_saturate16(shifted);
}
#define SROUND16(x,a) e907_sround16((opus_val32)(x),(int)(a))

/* MULT16_16_Q15: (a * b) >> 15  (Q15 fractional multiply).
 * Generic: mul + srai = 2 instructions
 * E907:    khmbb       = 1 instruction (bottom-half × bottom-half >> 15) */
#undef MULT16_16_Q15
static OPUS_INLINE opus_val32 e907_mult16_16_q15(opus_val32 a, opus_val32 b)
{
    opus_val32 res;
    __asm__ volatile("khmbb %0, %1, %2" : "=r"(res) : "r"(a), "r"(b));
    return res;
}
#define MULT16_16_Q15(a,b) e907_mult16_16_q15((opus_val32)(opus_val16)(a),(opus_val32)(opus_val16)(b))

/* MULT16_16_P15: rounding version of Q15 multiply.
 * Generic: SHR(ADD32(16384, MULT16_16(a,b)), 15) = 4 instructions
 * E907:    mul + sra.u                            = 2 instructions  */
#undef MULT16_16_P15
#define MULT16_16_P15(a,b) (PSHR(MULT16_16((a),(b)), 15))

/* MAC16_32_Q15: c + (a16 * b32) >> 15.
 * Generic: decomposes b into hi/lo halves = 6-8 instructions
 * E907:    kmmwb2 + add                   = 2 instructions          */
#undef MAC16_32_Q15
#define MAC16_32_Q15(c,a,b) ADD32((c), MULT16_32_Q15((a),(b)))

/* MAC16_32_Q16: c + (a16 * b32) >> 16.
 * Generic: decomposes b into hi/lo halves = 6-8 instructions
 * E907:    smmwb + add                    = 2 instructions          */
#undef MAC16_32_Q16
#define MAC16_32_Q16(c,a,b) ADD32((c), MULT16_32_Q16((a),(b)))

#endif /* E907_OPUS_DSP primitive overrides */

#if defined(E907_OPUS_DSP)
static OPUS_INLINE opus_val16 SIG2WORD16_e907(celt_sig x)
{
   opus_int32 shifted = PSHR32(x, SIG_SHIFT);
   opus_int32 res;
   __asm__ volatile("sclip32 %0, %1, 15" : "=r"(res) : "r"(shifted));
   return (opus_val16)res;
}
#define SIG2WORD16(x) (SIG2WORD16_e907(x))
#else
static OPUS_INLINE opus_val16 SIG2WORD16_generic(celt_sig x)
{
   x = PSHR32(x, SIG_SHIFT);
   x = MAX32(x, -32768);
   x = MIN32(x, 32767);
   return EXTRACT16(x);
}
#define SIG2WORD16(x) (SIG2WORD16_generic(x))
#endif

#endif
