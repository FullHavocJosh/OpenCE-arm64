/* Spike: can a macOS arm64 process map, execute and fault-trap memory at 0x88000000?
 *
 * Build: clang -O2 -Wl,-pagezero_size,0x4000 -Wl,-image_base,0x100000000 lowmap.c -o lowmap
 */
#include <libkern/OSCacheControl.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <unistd.h>

#define LOW_ADDR ((void *)0x88000000u)
#define LOW_SIZE 0x8000u

static volatile sig_atomic_t g_signal;
static volatile uintptr_t g_page;
static volatile size_t g_page_size;

static void fault_handler(int sig, siginfo_t *info, void *ctx)
{
    (void)ctx;
    g_signal = sig;
    if (mprotect((void *)g_page, g_page_size, PROT_READ | PROT_WRITE) != 0)
        _exit(2);
    (void)info;
}

int main(void)
{
    size_t page = (size_t)getpagesize();
    setvbuf(stdout, NULL, _IONBF, 0);
    uint32_t *code = mmap(LOW_ADDR, LOW_SIZE, PROT_READ | PROT_WRITE,
                          MAP_FIXED | MAP_PRIVATE | MAP_ANON, -1, 0);
    if (code == MAP_FAILED || (void *)code != LOW_ADDR) {
        perror("mmap 0x88000000");
        return 1;
    }
    printf("mapped %p\n", (void *)code);

    code[0] = 0x52800540; /* mov w0, #42 */
    code[1] = 0xd65f03c0; /* ret */
    sys_icache_invalidate(code, LOW_SIZE);
    if (mprotect(code, LOW_SIZE, PROT_READ | PROT_EXEC) != 0) {
        perror("mprotect rx");
        return 1;
    }
    int (*fn)(void) = (int (*)(void))(void *)code;
    int rc = fn();
    printf("stub returned: %d\n", rc);
    if (rc != 42)
        return 1;

    void *ro = mmap(NULL, page, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANON, -1, 0);
    if (ro == MAP_FAILED) {
        perror("mmap ro page");
        return 1;
    }
    if (mprotect(ro, page, PROT_READ) != 0) {
        perror("mprotect ro");
        return 1;
    }
    g_page = (uintptr_t)ro;
    g_page_size = page;

    struct sigaction sa = {0};
    sa.sa_sigaction = fault_handler;
    sa.sa_flags = SA_SIGINFO;
    sigemptyset(&sa.sa_mask);
    if (sigaction(SIGSEGV, &sa, NULL) != 0 || sigaction(SIGBUS, &sa, NULL) != 0) {
        perror("sigaction");
        return 1;
    }

    *(volatile uint8_t *)ro = 1;

    if (g_signal == SIGSEGV)
        printf("fault signal: SIGSEGV\n");
    else if (g_signal == SIGBUS)
        printf("fault signal: SIGBUS\n");
    else {
        printf("fault signal: none\n");
        return 1;
    }
    printf("page size: %zu\n", page);
    return 0;
}
