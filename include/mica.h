/* MICA v1.0 freestanding ABI proposal; declarations for a FUTURE C compiler.
 * No C compiler, linker or ISO C hosted library is provided. MIT. */
#ifndef MICA_H
#define MICA_H
#include <stddef.h>
#include <stdint.h>
#define MICA_UART_TX ((uintptr_t)0xffff0000u)
#define MICA_HOST_EXIT ((uintptr_t)0xffff0004u)
#define MICA_CYCLE_COUNTER ((uintptr_t)0xffff0008u)
#define MICA_STACK_ALIGN 16u
#ifdef __cplusplus
extern "C" {
#endif
void *mica_memcpy(void *,const void *,size_t);
void *mica_memmove(void *,const void *,size_t);
void *mica_memset(void *,int,size_t);
size_t mica_strlen(const char *);
size_t mica_strnlen(const char *,size_t);
char *mica_strcpy(char *,const char *);
char *mica_strncpy(char *,const char *,size_t);
int mica_memcmp(const void *,const void *,size_t);
int mica_strcmp(const char *,const char *);
char *mica_strchr(const char *,int);
/* mica_udivmod has a dual-register return, so it needs compiler lowering,
 * rather than claiming compatibility with a conventional C ABI. */
unsigned mica_popcount(unsigned long);
unsigned mica_clz(unsigned long);
void mica_spin_lock(volatile unsigned long *);
void mica_spin_unlock(volatile unsigned long *);
unsigned long mica_fetch_add(volatile unsigned long *,unsigned long);
/* Future C signatures, pending a real MICA C compiler and linker. */
uint32_t mica_crc32(const void *,size_t);
void mica_arena_init(void *,size_t);
void *mica_arena_alloc(size_t);
void *mica_memchr(const void *,int,size_t);
void *mica_memrchr(const void *,int,size_t);
int mica_strncmp(const char *,const char *,size_t);
#ifdef __cplusplus
}
#endif
#endif
/* The v1.0 SDK also supplies console32/console64.mica and ctype.mica.
 * They are assembly-linkable only; no C runtime is actually linked. */
