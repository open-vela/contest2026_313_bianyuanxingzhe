"""Exercise DMA wrap and unread-data preservation using the driver helper."""
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
HEADER = ROOT / "board_overlay/sf32lb52_devkit_lcd/patches"


class RxStabilityTests(unittest.TestCase):
    def test_console_reader_finishes_fragment_without_poll_edge(self):
        text = (ROOT / "app/edge_walker/ew_serial_ctl.c").read_text(encoding="utf-8")
        body = text[text.index("static void *ctl_reader("):text.index("void ew_serial_ctl_start(")]
        source = r'''
#include <assert.h>
#include <setjmp.h>
#include <stdint.h>
#include <string.h>
#include <sys/types.h>
#define EW_CTL_LINE_MAX 768
struct pollfd { int fd, events; };
#define POLLIN 1
int poll(struct pollfd *p,int n,int ms) { (void)p;(void)n;(void)ms;return 0; }
static jmp_buf done;
static unsigned position, ready=24, slept, lines;
static const char wire[]="@alert none\r\n@road id poll\r\n";
static ssize_t fake_read(int fd,void *out,size_t n) {
  (void)fd;(void)n;
  if (position>=ready) return -1;
  *(char *)out=wire[position++]; return 1;
}
static void fake_usleep(unsigned us) {
  slept+=us;
  ready=sizeof(wire)-1; /* missing suffix becomes visible without a poll event */
  assert(slept<=20000);
}
static void q_push(const char *line) {
  assert(!strcmp(line,lines ? "road id poll":"alert none"));
  if (++lines==2) longjmp(done,1);
}
#define read fake_read
#define usleep fake_usleep
'''
        source += body
        source += r'''
int main(void) {
  if (!setjmp(done)) ctl_reader((void *)(intptr_t)7);
  assert(lines==2 && slept>0 && slept<=20000);
  return 0;
}
'''
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "reader.c"
            exe = Path(d) / ("reader.exe" if os.name == "nt" else "reader")
            src.write_text(source)
            subprocess.run(["gcc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                            str(src), "-o", str(exe)], check=True)
            subprocess.run([str(exe)], check=True, timeout=3)

    def test_idle_arriving_during_drain_is_not_erased(self):
        patch = (HEADER / "uart_dma_rx_ring.patch").read_text()
        bodies = []
        for remove in ("+", "-"):
            side = "\n".join(line[1:] for line in patch.splitlines()
                             if line[:1] in (" ", remove)
                             and not line.startswith(("+++", "---")))
            match = re.search(r"/\* DMA RX IDLE interrupt \*/(.*?)/\* (?:Bound each TX|DMA TX)", side, re.S)
            self.assertIsNotNone(match)
            bodies.append(match[1])
        source = r'''
#include <assert.h>
#define RESET 0
#define UART_FLAG_IDLE 1
typedef struct { int idle; } Handle;
struct Port { int uart_rx_dma_flag; Handle handle; };
#define __HAL_UART_GET_FLAG(h, f) ((h)->idle)
#define __HAL_UART_CLEAR_IDLEFLAG(h) ((h)->idle=0)
/* A second burst finishes while the first DMA buffer is being drained. */
static void HAL_UART_RxCpltCallback(Handle *h) { h->idle=1; }
'''
        source += "\nstatic void fixed(struct Port *uart) {" + bodies[0] + "}\n"
        source += "static void before(struct Port *uart) {" + bodies[1] + "}\n"
        source += r'''
int main(void) {
  struct Port p={1,{1}};
  before(&p); assert(p.handle.idle==0); /* old code loses the new wakeup */
  p.handle.idle=1;
  fixed(&p); assert(p.handle.idle==1);  /* new code leaves it pending */
  return 0;
}
'''
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "idle.c"
            exe = Path(d) / ("idle.exe" if os.name == "nt" else "idle")
            src.write_text(source)
            subprocess.run(["gcc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                            str(src), "-o", str(exe)], check=True)
            subprocess.run([str(exe)], check=True, timeout=10)

    def test_production_dma_callback_normalizes_transfer_complete_boundary(self):
        patch = (HEADER / "uart_dma_rx_ring.patch").read_text(encoding="utf-8")
        side = "\n".join(line[1:] for line in patch.splitlines()
                         if line[:1] in (" ", "+") and not line.startswith("+++"))
        callback = re.search(r"void HAL_UART_RxHalfCpltCallback\(.*?\n\}", side, re.S)
        self.assertIsNotNone(callback)
        source = r'''
#include <assert.h>
#include <stdint.h>
#include "ew_uart_diag.h"
typedef int irqstate_t;
typedef struct { unsigned unused; } UART_HandleTypeDef;
struct uart_dev_s { struct { int head,tail,size;char *buffer; } recv; };
struct sifli_uart { UART_HandleTypeDef handle;
 struct { struct { unsigned counter; } handle; unsigned last_index; } dma_rx;
 struct uart_dev_s serial; };
static struct sifli_uart uart_obj[1];
static ew_uart_rx_diag_t g_uart_rx_diag[1];
static unsigned notifications;
static irqstate_t enter_critical_section(void) { return 0; }
static void leave_critical_section(int n) { (void)n; }
static void up_invalidate_dcache(uintptr_t a,uintptr_t b) { assert(b-a==16); }
static void uart_datareceived(struct uart_dev_s *d) {
 assert(d->recv.head>=0 && d->recv.head<d->recv.size);notifications++;
}
#define __HAL_DMA_GET_COUNTER(h) ((h)->counter)
'''
        source += callback[0]
        source += r'''
int main(void) {
 char buf[16];struct sifli_uart *p=&uart_obj[0];
 p->serial.recv.size=16;p->serial.recv.buffer=buf;
 p->dma_rx.handle.counter=8;HAL_UART_RxHalfCpltCallback(&p->handle);
 assert(p->serial.recv.head==8 && notifications==1);
 p->dma_rx.handle.counter=0;HAL_UART_RxHalfCpltCallback(&p->handle);
 assert(p->serial.recv.head==0 && notifications==2 && g_uart_rx_diag[0].dma_bytes==16);
 p->dma_rx.handle.counter=16;HAL_UART_RxHalfCpltCallback(&p->handle);
 assert(p->serial.recv.head==0 && notifications==2 && g_uart_rx_diag[0].dma_bytes==16);
 p->dma_rx.handle.counter=13;HAL_UART_RxHalfCpltCallback(&p->handle);
 assert(p->serial.recv.head==3 && notifications==3 && g_uart_rx_diag[0].dma_bytes==19);
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "boundary.c"
            exe = Path(d) / ("boundary.exe" if os.name == "nt" else "boundary")
            src.write_text(source)
            subprocess.run(["gcc", "-std=c99", "-Wall", "-Wextra", "-Werror",
                            "-I", str(ROOT / "app/edge_walker"), str(src), "-o", str(exe)], check=True)
            subprocess.run([str(exe)], check=True, timeout=3)


if __name__ == "__main__":
    unittest.main()
