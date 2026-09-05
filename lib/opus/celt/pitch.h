/* Copyright (c) 2007-2008 CSIRO
   Copyright (c) 2007-2009 Xiph.Org Foundation
   Written by Jean-Marc Valin */
/**
   @file pitch.h
   @brief Pitch analysis
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

#ifndef PITCH_H
#define PITCH_H

#include "modes.h"
#include "cpu_support.h"

#if (defined(OPUS_X86_MAY_HAVE_SSE) && !defined(FIXED_POINT)) \
  || ((defined(OPUS_X86_MAY_HAVE_SSE4_1) || defined(OPUS_X86_MAY_HAVE_SSE2)) && defined(FIXED_POINT))
#include "x86/pitch_sse.h"
#endif

#if defined(FIXED_POINT) && defined(__mips)
#include "mips/pitch_mipsr1.h"
#endif

#if (defined(OPUS_ARM_ASM) || defined(OPUS_ARM_MAY_HAVE_NEON_INTR))
# include "arm/pitch_arm.h"
#endif

void pitch_downsample(celt_sig * OPUS_RESTRICT x[], opus_val16 * OPUS_RESTRICT x_lp,
      int len, int C, int factor, int arch);

void pitch_search(const opus_val16 * OPUS_RESTRICT x_lp, opus_val16 * OPUS_RESTRICT y,
                  int len, int max_pitch, int *pitch, int arch);

opus_val16 remove_doubling(opus_val16 *x, int maxperiod, int minperiod,
      int N, int *T0, int prev_period, opus_val16 prev_gain, int arch);


/* OPT: This is the kernel you really want to optimize. It gets used a lot
   by the prefilter and by the PLC. */
static OPUS_INLINE void xcorr_kernel_c(const opus_val16 * x, const opus_val16 * y, opus_val32 sum[4], int len)
{
   int j;
   opus_val16 y_0, y_1, y_2, y_3;
   celt_assert(len>=3);
   y_3=0; /* gcc doesn't realize that y_3 can't be used uninitialized */
   y_0=*y++;
   y_1=*y++;
   y_2=*y++;
   for (j=0;j<len-3;j+=4)
   {
      opus_val16 tmp;
      tmp = *x++;
      y_3=*y++;
      sum[0] = MAC16_16(sum[0],tmp,y_0);
      sum[1] = MAC16_16(sum[1],tmp,y_1);
      sum[2] = MAC16_16(sum[2],tmp,y_2);
      sum[3] = MAC16_16(sum[3],tmp,y_3);
      tmp=*x++;
      y_0=*y++;
      sum[0] = MAC16_16(sum[0],tmp,y_1);
      sum[1] = MAC16_16(sum[1],tmp,y_2);
      sum[2] = MAC16_16(sum[2],tmp,y_3);
      sum[3] = MAC16_16(sum[3],tmp,y_0);
      tmp=*x++;
      y_1=*y++;
      sum[0] = MAC16_16(sum[0],tmp,y_2);
      sum[1] = MAC16_16(sum[1],tmp,y_3);
      sum[2] = MAC16_16(sum[2],tmp,y_0);
      sum[3] = MAC16_16(sum[3],tmp,y_1);
      tmp=*x++;
      y_2=*y++;
      sum[0] = MAC16_16(sum[0],tmp,y_3);
      sum[1] = MAC16_16(sum[1],tmp,y_0);
      sum[2] = MAC16_16(sum[2],tmp,y_1);
      sum[3] = MAC16_16(sum[3],tmp,y_2);
   }
   if (j++<len)
   {
      opus_val16 tmp = *x++;
      y_3=*y++;
      sum[0] = MAC16_16(sum[0],tmp,y_0);
      sum[1] = MAC16_16(sum[1],tmp,y_1);
      sum[2] = MAC16_16(sum[2],tmp,y_2);
      sum[3] = MAC16_16(sum[3],tmp,y_3);
   }
   if (j++<len)
   {
      opus_val16 tmp=*x++;
      y_0=*y++;
      sum[0] = MAC16_16(sum[0],tmp,y_1);
      sum[1] = MAC16_16(sum[1],tmp,y_2);
      sum[2] = MAC16_16(sum[2],tmp,y_3);
      sum[3] = MAC16_16(sum[3],tmp,y_0);
   }
   if (j<len)
   {
      opus_val16 tmp=*x++;
      y_1=*y++;
      sum[0] = MAC16_16(sum[0],tmp,y_2);
      sum[1] = MAC16_16(sum[1],tmp,y_3);
      sum[2] = MAC16_16(sum[2],tmp,y_0);
      sum[3] = MAC16_16(sum[3],tmp,y_1);
   }
}

#if defined(E907_OPUS_DSP) && defined(FIXED_POINT)
/*
 * E907 P-extension optimized pitch correlation functions.
 *
 * Key instruction: kmda rd, rs1, rs2
 *   rd = rs1[15:0]*rs2[15:0] + rs1[31:16]*rs2[31:16]
 *   Two 16x16 MACs in a single instruction.
 *
 * By loading two consecutive int16 values as one 32-bit word (little-endian),
 * we process 2 elements per kmda, halving the loop iterations.
 *
 * pkbt16 rd, rs1, rs2 constructs shifted packed values:
 *   rd = {rs1[15:0], rs2[31:16]}
 * Used in xcorr_kernel to build odd-aligned y[] pairs.
 */

static OPUS_INLINE opus_val32 celt_inner_prod_e907(const opus_val16 *x,
      const opus_val16 *y, int N)
{
   int i;
   opus_val32 xy = 0;
   for (i = 0; i + 3 < N; i += 4) {
      opus_val32 p0, p1;
      __asm__ volatile("kmda %0, %1, %2" : "=r"(p0)
          : "r"(*(const opus_val32*)(x+i)), "r"(*(const opus_val32*)(y+i)));
      __asm__ volatile("kmda %0, %1, %2" : "=r"(p1)
          : "r"(*(const opus_val32*)(x+i+2)), "r"(*(const opus_val32*)(y+i+2)));
      xy += p0 + p1;
   }
   for (; i < N; i++)
      xy = MAC16_16(xy, x[i], y[i]);
   return xy;
}

static OPUS_INLINE void dual_inner_prod_e907(const opus_val16 *x,
      const opus_val16 *y01, const opus_val16 *y02,
      int N, opus_val32 *xy1, opus_val32 *xy2)
{
   int i;
   opus_val32 s1 = 0, s2 = 0;
   for (i = 0; i + 3 < N; i += 4) {
      opus_val32 px0 = *(const opus_val32*)(x+i);
      opus_val32 px1 = *(const opus_val32*)(x+i+2);
      opus_val32 p0, p1, p2, p3;
      __asm__ volatile("kmda %0, %1, %2" : "=r"(p0)
          : "r"(px0), "r"(*(const opus_val32*)(y01+i)));
      __asm__ volatile("kmda %0, %1, %2" : "=r"(p1)
          : "r"(px1), "r"(*(const opus_val32*)(y01+i+2)));
      __asm__ volatile("kmda %0, %1, %2" : "=r"(p2)
          : "r"(px0), "r"(*(const opus_val32*)(y02+i)));
      __asm__ volatile("kmda %0, %1, %2" : "=r"(p3)
          : "r"(px1), "r"(*(const opus_val32*)(y02+i+2)));
      s1 += p0 + p1;
      s2 += p2 + p3;
   }
   for (; i < N; i++) {
      s1 = MAC16_16(s1, x[i], y01[i]);
      s2 = MAC16_16(s2, x[i], y02[i]);
   }
   *xy1 = s1;
   *xy2 = s2;
}

static OPUS_INLINE void xcorr_kernel_e907(const opus_val16 *x,
      const opus_val16 *y, opus_val32 sum[4], int len)
{
   int j;
   /* Process 2 x-elements per iteration.
    * sum[k] = Σ x[j]*y[j+k], k=0..3
    * For each pair (x[j], x[j+1]), we need y words at offsets 0,1,2,3,4.
    * Word loads give even-aligned pairs; pkbt16 constructs odd-aligned pairs. */
   for (j = 0; j + 1 < len; j += 2) {
      opus_val32 px  = *(const opus_val32*)(x + j);
      opus_val32 wy0 = *(const opus_val32*)(y + j);
      opus_val32 wy1 = *(const opus_val32*)(y + j + 2);
      opus_val32 ry1, ry3, p;
      /* {y[j+2], y[j+1]}: B(wy1)=y[j+2] → top, T(wy0)=y[j+1] → bottom */
      __asm__ volatile("pkbt16 %0, %1, %2" : "=r"(ry1) : "r"(wy1), "r"(wy0));
      /* {y[j+4], y[j+3]}: only load y[j+4], reuse T(wy1)=y[j+3] */
      __asm__ volatile("pkbt16 %0, %1, %2" : "=r"(ry3)
          : "r"((opus_val32)y[j+4]), "r"(wy1));

      __asm__ volatile("kmda %0, %1, %2" : "=r"(p) : "r"(px), "r"(wy0));
      sum[0] += p;
      __asm__ volatile("kmda %0, %1, %2" : "=r"(p) : "r"(px), "r"(ry1));
      sum[1] += p;
      __asm__ volatile("kmda %0, %1, %2" : "=r"(p) : "r"(px), "r"(wy1));
      sum[2] += p;
      __asm__ volatile("kmda %0, %1, %2" : "=r"(p) : "r"(px), "r"(ry3));
      sum[3] += p;
   }
   if (j < len) {
      opus_val16 tmp = x[j];
      sum[0] = MAC16_16(sum[0], tmp, y[j]);
      sum[1] = MAC16_16(sum[1], tmp, y[j+1]);
      sum[2] = MAC16_16(sum[2], tmp, y[j+2]);
      sum[3] = MAC16_16(sum[3], tmp, y[j+3]);
   }
}

#define OVERRIDE_XCORR_KERNEL
#define xcorr_kernel(x, y, sum, len, arch) \
    ((void)(arch),xcorr_kernel_e907(x, y, sum, len))

#define OVERRIDE_DUAL_INNER_PROD
#define dual_inner_prod(x, y01, y02, N, xy1, xy2, arch) \
    ((void)(arch),dual_inner_prod_e907(x, y01, y02, N, xy1, xy2))

#define OVERRIDE_CELT_INNER_PROD
#define celt_inner_prod(x, y, N, arch) \
    ((void)(arch),celt_inner_prod_e907(x, y, N))

#else /* !E907_OPUS_DSP || !FIXED_POINT */

#ifndef OVERRIDE_XCORR_KERNEL
#define xcorr_kernel(x, y, sum, len, arch) \
    ((void)(arch),xcorr_kernel_c(x, y, sum, len))
#endif /* OVERRIDE_XCORR_KERNEL */

#endif /* E907_OPUS_DSP && FIXED_POINT */


static OPUS_INLINE void dual_inner_prod_c(const opus_val16 *x, const opus_val16 *y01, const opus_val16 *y02,
      int N, opus_val32 *xy1, opus_val32 *xy2)
{
   int i;
   opus_val32 xy01=0;
   opus_val32 xy02=0;
   for (i=0;i<N;i++)
   {
      xy01 = MAC16_16(xy01, x[i], y01[i]);
      xy02 = MAC16_16(xy02, x[i], y02[i]);
   }
   *xy1 = xy01;
   *xy2 = xy02;
}

#ifndef OVERRIDE_DUAL_INNER_PROD
# define dual_inner_prod(x, y01, y02, N, xy1, xy2, arch) \
    ((void)(arch),dual_inner_prod_c(x, y01, y02, N, xy1, xy2))
#endif

/*We make sure a C version is always available for cases where the overhead of
  vectorization and passing around an arch flag aren't worth it.*/
static OPUS_INLINE opus_val32 celt_inner_prod_c(const opus_val16 *x,
      const opus_val16 *y, int N)
{
   int i;
   opus_val32 xy=0;
   for (i=0;i<N;i++)
      xy = MAC16_16(xy, x[i], y[i]);
   return xy;
}

#if !defined(OVERRIDE_CELT_INNER_PROD)
# define celt_inner_prod(x, y, N, arch) \
    ((void)(arch),celt_inner_prod_c(x, y, N))
#endif

#ifdef NON_STATIC_COMB_FILTER_CONST_C
void comb_filter_const_c(opus_val32 *y, opus_val32 *x, int T, int N,
     opus_val16 g10, opus_val16 g11, opus_val16 g12);
#endif


#ifdef FIXED_POINT
opus_val32
#else
void
#endif
celt_pitch_xcorr_c(const opus_val16 *_x, const opus_val16 *_y,
      opus_val32 *xcorr, int len, int max_pitch, int arch);

#ifndef OVERRIDE_PITCH_XCORR
# define celt_pitch_xcorr celt_pitch_xcorr_c
#endif

#ifdef NON_STATIC_COMB_FILTER_CONST_C
void comb_filter_const_c(opus_val32 *y, opus_val32 *x, int T, int N,
                         opus_val16 g10, opus_val16 g11, opus_val16 g12);
#endif

#ifndef OVERRIDE_COMB_FILTER_CONST
# define comb_filter_const(y, x, T, N, g10, g11, g12, arch) \
    ((void)(arch),comb_filter_const_c(y, x, T, N, g10, g11, g12))
#endif


#endif
