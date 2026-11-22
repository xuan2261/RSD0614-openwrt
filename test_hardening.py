"""Parser/source regressions only. Synthetic fixtures never count as a hardware test."""
from pathlib import Path
import hashlib,json,lzma,re,struct,subprocess,tempfile,unittest
import deep_audit as da
import harden_source as hs
ROOT=Path(__file__).resolve().parent

UART_PATCH_STACK=(
    ROOT/'fixtures/openwrt-realtek/0004-rtl8197f-dw-uart.patch',
    ROOT/'patches'/hs.UART_PATCH_NAME,
    ROOT/'patches'/hs.UART_DIAG_PATCH_NAME,
    ROOT/'patches'/hs.UART_FIX_PATCH_NAME,
)

def build_patched_dw8250():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);rel='drivers/tty/serial/8250/8250_dw.c'
        src=ROOT/'fixtures/linux-4.14.187'/rel;dst=root/rel
        dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(src.read_bytes())
        for patch in UART_PATCH_STACK:
            r=subprocess.run(['patch','--batch','--fuzz=0','-p1','-i',str(patch)],cwd=td,text=True,capture_output=True)
            if r.returncode!=0:
                raise RuntimeError(f'Patch {patch.name} failed:\n{r.stdout}{r.stderr}')
        return dst.read_bytes()

DW8250_SIM_STUB_H = r"""#ifndef STUB_COMMON_H
#define STUB_COMMON_H
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
typedef unsigned long resource_size_t;

#define __iomem
#define BIT(nr) (1UL << (nr))
#define EINVAL 22
#define ENOMEM 12
#define ENOENT 2
#define EPROBE_DEFER 517
#define GFP_KERNEL 0
#define KERN_ERR "<3>"

#define IS_ERR(p) ((uintptr_t)(p) >= (uintptr_t)-4095UL)
#define PTR_ERR(p) ((long)(intptr_t)(p))
#define ERR_PTR(e) ((void *)(intptr_t)(e))
#define IS_ERR_OR_NULL(p) (!(p) || IS_ERR(p))
#define container_of(ptr, type, member) ((type *)((char *)(ptr) - offsetof(type, member)))

struct spinlock { int dummy; };
typedef struct spinlock spinlock_t;
#define spin_lock_init(l) do { (l)->dummy = 0; } while (0)
#define spin_lock_irqsave(l, f) do { (void)(l); (f) = 0; } while (0)
#define spin_unlock_irqrestore(l, f) do { (void)(l); (void)(f); } while (0)

struct device_node { const char *compat; };
struct acpi_device_id { const char *id; unsigned long driver_data; };
struct device_driver { const struct acpi_device_id *acpi_match_table; const char *name; const void *pm; const void *of_match_table; };
struct device { struct device_node *of_node; struct device *parent; struct device_driver *driver; void *driver_data; };
struct resource { resource_size_t start; resource_size_t end; const char *name; };
#define IORESOURCE_MEM 0x200
static inline resource_size_t resource_size(const struct resource *r) { return r->end - r->start + 1; }

struct platform_device { struct device dev; struct resource res; int irq; };
#define to_platform_device(d) container_of(d, struct platform_device, dev)

static inline void dev_err(const struct device *dev, const char *fmt, ...) { (void)dev; (void)fmt; }
static inline void dev_warn(const struct device *dev, const char *fmt, ...) { (void)dev; (void)fmt; }
static inline void dev_dbg(const struct device *dev, const char *fmt, ...) { (void)dev; (void)fmt; }
extern char g_last_dev_info[256];
static inline void dev_info(const struct device *dev, const char *fmt, ...) {
    va_list ap;
    (void)dev;
    va_start(ap, fmt);
    vsnprintf(g_last_dev_info, sizeof(g_last_dev_info), fmt, ap);
    va_end(ap);
}
extern int g_printk_count;
static inline int printk_deferred(const char *fmt, ...) { (void)fmt; g_printk_count++; return 0; }

extern u32 sim_mmio_read32(const volatile void __iomem *addr);
extern void sim_mmio_write32(u32 val, volatile void __iomem *addr);
extern u8 sim_mmio_read8(const volatile void __iomem *addr);
extern void sim_mmio_write8(u8 val, volatile void __iomem *addr);

#define readl(a) sim_mmio_read32(a)
#define writel(v, a) sim_mmio_write32((u32)(v), (a))
#define ioread32be(a) sim_mmio_read32(a)
#define iowrite32be(v, a) sim_mmio_write32((u32)(v), (a))
#define readb(a) sim_mmio_read8(a)
#define writeb(v, a) sim_mmio_write8((u8)(v), (a))
static inline void iounmap(volatile void __iomem *addr) { (void)addr; }
static inline void __iomem *devm_ioremap(struct device *dev, resource_size_t offset, resource_size_t size) {
    (void)dev; (void)size; return (void __iomem *)(uintptr_t)offset;
}
static inline void *devm_kzalloc(struct device *dev, size_t size, int flags) {
    (void)dev; (void)flags; return calloc(1, size);
}

struct of_device_id { char compatible[64]; };
#define MODULE_DEVICE_TABLE(t, n)
#define MODULE_AUTHOR(s)
#define MODULE_LICENSE(s)
#define MODULE_DESCRIPTION(s)
#define MODULE_ALIAS(s)
#define ACPI_PTR(x) (x)
#define SET_SYSTEM_SLEEP_PM_OPS(s, r)
#define SET_RUNTIME_PM_OPS(s, r, i)
struct dev_pm_ops { int dummy; };
struct platform_driver {
    struct device_driver driver;
    int (*probe)(struct platform_device *);
    int (*remove)(struct platform_device *);
};
#define module_platform_driver(d)

extern struct device_node g_sysc_node;
extern void __iomem *g_sysc_base;
extern bool g_sysc_present;
extern int g_of_node_put_count;

static inline int of_alias_get_id(struct device_node *np, const char *stem) { (void)np; (void)stem; return 0; }
static inline bool of_device_is_compatible(const struct device_node *np, const char *compat) {
    return np && np->compat && strcmp(np->compat, compat) == 0;
}
static inline bool of_device_is_big_endian(const struct device_node *np) { (void)np; return false; }
static inline struct device_node *of_find_compatible_node(struct device_node *from, const char *type, const char *compat) {
    (void)from; (void)type;
    if (g_sysc_present && strcmp(compat, "realtek,rtl819x-sysc") == 0)
        return &g_sysc_node;
    return NULL;
}
static inline void __iomem *of_iomap(struct device_node *np, int index) {
    (void)index;
    return (np == &g_sysc_node) ? g_sysc_base : NULL;
}
static inline void of_node_put(struct device_node *np) {
    if (np == &g_sysc_node) g_of_node_put_count++;
}

static inline bool has_acpi_companion(struct device *dev) { (void)dev; return false; }
static inline const struct acpi_device_id *acpi_match_device(const struct acpi_device_id *ids, const struct device *dev) {
    (void)ids; (void)dev; return NULL;
}
static inline struct resource *platform_get_resource(struct platform_device *dev, unsigned int type, unsigned int num) {
    (void)type; return (num == 0) ? &dev->res : NULL;
}
static inline struct resource *platform_get_resource_byname(struct platform_device *dev, unsigned int type, const char *name) {
    (void)dev; (void)type; (void)name; return NULL;
}
static inline int platform_get_irq(struct platform_device *dev, unsigned int num) {
    return (num == 0) ? dev->irq : -EINVAL;
}
static inline void platform_set_drvdata(struct platform_device *pdev, void *data) { pdev->dev.driver_data = data; }
static inline void *platform_get_drvdata(const struct platform_device *pdev) { return pdev->dev.driver_data; }
static inline void *dev_get_drvdata(const struct device *dev) { return dev->driver_data; }

static inline bool device_property_read_bool(struct device *dev, const char *propname) { (void)dev; (void)propname; return false; }
static inline int device_property_read_u32(struct device *dev, const char *propname, u32 *val) {
    (void)dev;
    if (strcmp(propname, "reg-shift") == 0) { *val = 2; return 0; }
    if (strcmp(propname, "reg-io-width") == 0) { *val = 4; return 0; }
    if (strcmp(propname, "clock-frequency") == 0) { *val = 100000000; return 0; }
    return -EINVAL;
}

struct clk { unsigned long rate; };
static inline struct clk *devm_clk_get(struct device *dev, const char *id) { (void)dev; (void)id; return (struct clk *)ERR_PTR(-ENOENT); }
static inline int clk_prepare_enable(struct clk *clk) { (void)clk; return 0; }
static inline void clk_disable_unprepare(struct clk *clk) { (void)clk; }
static inline unsigned long clk_get_rate(struct clk *clk) { return clk ? clk->rate : 0; }
static inline long clk_round_rate(struct clk *clk, unsigned long rate) { (void)clk; return (long)rate; }
static inline int clk_set_rate(struct clk *clk, unsigned long rate) { (void)clk; (void)rate; return 0; }

struct reset_control { int dummy; };
static inline struct reset_control *devm_reset_control_get_optional_exclusive(struct device *dev, const char *id) { (void)dev; (void)id; return NULL; }
static inline int reset_control_deassert(struct reset_control *rstc) { (void)rstc; return 0; }
static inline int reset_control_assert(struct reset_control *rstc) { (void)rstc; return 0; }

static inline void pm_runtime_get_sync(struct device *dev) { (void)dev; }
static inline void pm_runtime_put_sync_suspend(struct device *dev) { (void)dev; }
static inline void pm_runtime_set_active(struct device *dev) { (void)dev; }
static inline void pm_runtime_enable(struct device *dev) { (void)dev; }
static inline void pm_runtime_disable(struct device *dev) { (void)dev; }
static inline void pm_runtime_put_noidle(struct device *dev) { (void)dev; }

struct dma_device { struct device *dev; };
struct dma_chan { struct dma_device *device; };
struct dma_slave_config { u32 src_maxburst; u32 dst_maxburst; };

struct ktermios { unsigned int c_cflag; unsigned int c_line; };
#define CRTSCTS 020000000000
#define N_IRDA 11
static inline unsigned int tty_termios_baud_rate(struct ktermios *termios) { (void)termios; return 115200; }

#define PORT_8250 1
#define PORT_16550A 4
#define PORT_OCTEON 20
#define UPIO_MEM 2
#define UPIO_MEM32 3
#define UPIO_MEM32BE 6
#define UPF_SKIP_TEST (1U << 6)
#define UPF_SHARE_IRQ (1U << 24)
#define UPF_FIXED_TYPE (1U << 27)
#define UPF_FIXED_PORT (1U << 29)
#define UPSTAT_AUTOCTS (1U << 0)

#define UART_CAP_FIFO (1 << 8)
#define UART_CAP_AFE  (1 << 11)
#define UART_CAP_IRDA (1 << 14)

struct uart_port {
    spinlock_t lock;
    resource_size_t mapbase;
    unsigned char __iomem *membase;
    unsigned int (*serial_in)(struct uart_port *, int);
    void (*serial_out)(struct uart_port *, int, int);
    void (*set_termios)(struct uart_port *, struct ktermios *, struct ktermios *);
    void (*set_ldisc)(struct uart_port *, struct ktermios *);
    int (*handle_irq)(struct uart_port *);
    void (*pm)(struct uart_port *, unsigned int, unsigned int);
    unsigned int irq;
    unsigned int uartclk;
    unsigned int fifosize;
    unsigned char regshift;
    unsigned char iotype;
    unsigned int flags;
    unsigned int status;
    unsigned int type;
    int line;
    struct device *dev;
    void *private_data;
};

struct uart_8250_dma {
    bool (*fn)(struct dma_chan *chan, void *param);
    void *rx_param;
    void *tx_param;
    struct dma_slave_config rxconf;
    struct dma_slave_config txconf;
};

struct uart_8250_port {
    struct uart_port port;
    struct uart_8250_dma *dma;
    unsigned short capabilities;
    int (*dl_read)(struct uart_8250_port *);
    void (*dl_write)(struct uart_8250_port *, int);
};

#define up_to_u8250p(p) container_of(p, struct uart_8250_port, port)

extern int g_force_idle_count;
static inline void serial8250_clear_and_reinit_fifos(struct uart_8250_port *p) { (void)p; g_force_idle_count++; }
extern int g_serial8250_irq_handled;
static inline int serial8250_handle_irq(struct uart_port *p, unsigned int iir) { (void)p; (void)iir; return g_serial8250_irq_handled; }
static inline void serial8250_do_pm(struct uart_port *p, unsigned int s, unsigned int o) { (void)p; (void)s; (void)o; }
static inline void serial8250_do_set_termios(struct uart_port *p, struct ktermios *t, struct ktermios *o) { (void)p; (void)t; (void)o; }
static inline void serial8250_do_set_ldisc(struct uart_port *p, struct ktermios *t) { (void)p; (void)t; }
extern struct uart_8250_port g_registered_port;
static inline int serial8250_register_8250_port(struct uart_8250_port *up) { g_registered_port = *up; return 0; }
static inline void serial8250_unregister_port(int line) { (void)line; }
static inline void serial8250_suspend_port(int line) { (void)line; }
static inline void serial8250_resume_port(int line) { (void)line; }
#endif
"""

DW8250_SIM_MAIN_C = r"""#include "drivers/tty/serial/8250/8250_dw.c"
#include <assert.h>

#define UART_BASE_ADDR 0x18147000UL
#define SYSC_BASE_ADDR 0x18000000UL

char g_last_dev_info[256];
int g_printk_count;
int g_force_idle_count;
int g_serial8250_irq_handled;
struct uart_8250_port g_registered_port;
struct device_node g_sysc_node = { .compat = "realtek,rtl819x-sysc" };
void __iomem *g_sysc_base = (void __iomem *)SYSC_BASE_ADDR;
bool g_sysc_present = true;
int g_of_node_put_count;

static u32 g_soc_id;
static u32 g_uart_regs[64];
static int g_write_offsets[16];
static int g_write_count;

u32 sim_mmio_read32(const volatile void __iomem *addr)
{
    uintptr_t a = (uintptr_t)addr;
    if (a == SYSC_BASE_ADDR)
        return g_soc_id;
    assert(a >= UART_BASE_ADDR && a < UART_BASE_ADDR + sizeof(g_uart_regs));
    return g_uart_regs[(a - UART_BASE_ADDR) >> 2];
}

void sim_mmio_write32(u32 val, volatile void __iomem *addr)
{
    uintptr_t a = (uintptr_t)addr;
    assert(a >= UART_BASE_ADDR && a < UART_BASE_ADDR + sizeof(g_uart_regs));
    g_uart_regs[(a - UART_BASE_ADDR) >> 2] = val;
    if (g_write_count < 16)
        g_write_offsets[g_write_count++] = (int)(a - UART_BASE_ADDR);
}

u8 sim_mmio_read8(const volatile void __iomem *addr)
{
    return (u8)sim_mmio_read32(addr);
}

void sim_mmio_write8(u8 val, volatile void __iomem *addr)
{
    sim_mmio_write32(val, addr);
}

static void run_case(u32 soc_id, bool sysc_present, bool expect_non_vg)
{
    memset(g_uart_regs, 0, sizeof(g_uart_regs));
    memset(&g_registered_port, 0, sizeof(g_registered_port));
    memset(g_last_dev_info, 0, sizeof(g_last_dev_info));
    g_soc_id = soc_id;
    g_sysc_present = sysc_present;
    g_uart_regs[UART_LCR] = 0x03;
    g_force_idle_count = 0;
    g_printk_count = 0;
    g_of_node_put_count = 0;
    g_serial8250_irq_handled = 0;

    struct device_node uart_np = { .compat = "realtek,rtl8197f-uart" };
    struct platform_device pdev = {
        .dev = { .of_node = &uart_np },
        .res = { .start = UART_BASE_ADDR, .end = UART_BASE_ADDR + 0xff },
        .irq = 9,
    };

    int rc = dw8250_platform_driver.probe(&pdev);
    assert(rc == 0);
    assert(g_of_node_put_count == (sysc_present ? 1 : 0));

    struct uart_8250_port *up = &g_registered_port;
    struct uart_port *p = &up->port;
    struct dw8250_data *d = p->private_data;

    assert(d->is_rtl8197f == 1);
    assert(p->type == PORT_16550A);
    assert((p->flags & (UPF_SHARE_IRQ | UPF_FIXED_PORT | UPF_SKIP_TEST | UPF_FIXED_TYPE)) ==
           (UPF_SHARE_IRQ | UPF_FIXED_PORT | UPF_SKIP_TEST | UPF_FIXED_TYPE));
    assert(p->fifosize == 0);
    assert(up->dma == NULL);

    if (expect_non_vg) {
        assert(d->tx_reg == 9 && d->rx_reg == 9 && d->adjlcr == 1);
        assert(up->dl_read == rtl8197f_dl_read);
        assert(up->dl_write == rtl8197f_dl_write);
        assert(strstr(g_last_dev_info, "mode=non-vg tx_reg=9 rx_reg=9 adjlcr=1") != NULL);

        g_uart_regs[9] = 0xaa;
        up->dl_write(up, 0x0136);
        assert(g_uart_regs[UART_DLL] == 0x36);
        assert(g_uart_regs[UART_DLM] == 0x01);
        assert(g_uart_regs[9] == 0xaa);
        assert(up->dl_read(up) == 0x0136);

        g_write_count = 0;
        p->serial_out(p, UART_LCR, 0x13);
        assert(g_force_idle_count == 0);
        assert(g_uart_regs[UART_LCR] == 0x11 && d->last_lcr == 0x11);
        assert(g_write_count == 1 && g_write_offsets[0] == 0x0c);

        dw8250_serial_out(p, UART_LCR, 0x83);
        assert(g_force_idle_count == 0);
        assert(g_uart_regs[UART_LCR] == 0x81 && d->last_lcr == 0x81);

        dw8250_serial_out32be(p, UART_LCR, 0x0b);
        assert(g_force_idle_count == 0);
        assert(g_uart_regs[UART_LCR] == 0x09 && d->last_lcr == 0x09);

        g_write_count = 0;
        p->serial_out(p, UART_TX, 'Z');
        assert(g_write_count == 1 && g_write_offsets[0] == 0x24 && g_uart_regs[9] == 'Z');
    } else {
        assert(d->tx_reg == UART_TX && d->rx_reg == UART_RX && d->adjlcr == 0);
        assert(up->dl_read == NULL);
        assert(up->dl_write == NULL);
        assert(strstr(g_last_dev_info, "mode=vg-std tx_reg=0 rx_reg=0 adjlcr=0") != NULL);

        g_write_count = 0;
        p->serial_out(p, UART_LCR, 0x13);
        assert(g_force_idle_count == 0);
        assert(g_uart_regs[UART_LCR] == 0x13 && d->last_lcr == 0x13);
        assert(g_write_count == 1 && g_write_offsets[0] == 0x0c);

        dw8250_serial_out(p, UART_LCR, 0x83);
        assert(g_force_idle_count == 0);
        assert(g_uart_regs[UART_LCR] == 0x83 && d->last_lcr == 0x83);

        dw8250_serial_out32be(p, UART_LCR, 0x0b);
        assert(g_force_idle_count == 0);
        assert(g_uart_regs[UART_LCR] == 0x0b && d->last_lcr == 0x0b);

        g_write_count = 0;
        p->serial_out(p, UART_TX, 'A');
        assert(g_write_count == 1 && g_write_offsets[0] == 0x00 && g_uart_regs[0] == 'A');
    }

    u8 expected_lcr = d->last_lcr;
    g_uart_regs[UART_LCR] = 0x00;
    g_uart_regs[UART_IIR] = UART_IIR_BUSY;
    assert(p->handle_irq(p) == 1);
    assert(g_uart_regs[UART_LCR] == expected_lcr);

    g_uart_regs[UART_IIR] = UART_IIR_RX_TIMEOUT;
    g_uart_regs[UART_LSR] = UART_LSR_DR;
    for (int i = 1; i < 512; i++)
        (void)p->handle_irq(p);
    assert(d->diag_dumped == 1);
    assert(g_printk_count == 2);

    free(d);
}

int main(void)
{
    run_case(0x81970000U, true, false);
    run_case(0x81970001U, true, false);
    run_case(0x8197F000U, true, true);
    run_case(0x00000000U, false, false);
    return 0;
}
"""

def newc(name,body=b'',mode=0o100644,ino=1):
    name=name.encode()+b'\0';f=(ino,mode,0,0,1,0,len(body),0,0,0,0,len(name),0);header=b'070701'+b''.join(f'{x:08x}'.encode() for x in f)+name;header+=b'\0'*((-len(header))%4);return header+body+b'\0'*((-len(body))%4)
class ParserTests(unittest.TestCase):
 def test_cpio_regular_and_trailer(self):
  data=newc('init',b'hello')+newc('TRAILER!!!',ino=2);e,end=da.parse_cpio(data);self.assertEqual(e[0]['data'],b'hello');self.assertEqual(end,len(data))
 def test_cpio_symlink_only_parsed(self):
  data=newc('link',b'../init',0o120777)+newc('TRAILER!!!',ino=2);e,_=da.parse_cpio(data);self.assertEqual(e[0]['data'],b'../init')
 def test_cpio_path_traversal_rejected(self):
  for n in ('../x','/etc/passwd','x/../../y'):
   with self.subTest(n=n),self.assertRaises(ValueError):da.parse_cpio(newc(n))
 def test_cpio_truncation_rejected(self):
  with self.assertRaises(ValueError):da.parse_cpio(newc('init',b'abc')[:-1])
 def test_cpio_identical_duplicate_allowed_and_marked(self):
  data=newc('init')+newc('init',ino=2)+newc('TRAILER!!!',ino=3);e,_=da.parse_cpio(data);self.assertEqual(len(e),3);self.assertEqual(e[1]['duplicate_of_archive_offset'],0)
 def test_cpio_conflicting_duplicate_rejected(self):
  with self.assertRaises(ValueError):da.parse_cpio(newc('init',b'a')+newc('init',b'b',ino=2))
 def test_find_cpio_keeps_earliest_root_archive_with_safe_duplicates(self):
  parts=[newc('dev',mode=0o040755,ino=1)]+[newc(f'file{i:03d}',ino=i+10) for i in range(100)]+[newc('init',ino=200),newc('etc/inittab',ino=201),newc('dev',mode=0o040755,ino=202),newc('TRAILER!!!',ino=203)];entries,start,end=da.find_cpio(b''.join(parts));self.assertEqual(start,0);self.assertEqual(len(entries),105);self.assertEqual(entries[-2]['path'],'dev');self.assertIn('duplicate_of_archive_offset',entries[-2])
 def test_cpio_count_bounds(self):
  d=bytearray(newc('init'));d[94:102]=b'ffffffff'
  with self.assertRaises(ValueError):da.parse_cpio(bytes(d))
 def test_fdt_truncation_rejected(self):
  with self.assertRaises(ValueError):da.parse_fdt(b'\xd0\x0d\xfe\xed')
 def test_fdt_bounds_rejected(self):
  with self.assertRaises(ValueError):da.parse_fdt(struct.pack('>10I',0xd00dfeed,40,400,800,16,17,16,0,4,8))
 def test_no_lzma_rejected(self):
  with self.assertRaises(ValueError):da.unpack_lzma(bytes(65536))
 def test_lzma_actual_roundtrip(self):
  payload=b'Linux version fixture\0'+bytes(range(256))*300
  from lzma_test_fixture import load_fixture
  encoded=load_fixture();image=bytes(65536)+bytes(encoded)
  with self.assertRaises(ValueError):da.unpack_lzma(image)
  image=bytes(1024)+bytes(encoded)+bytes(65536);decoded,info=da.unpack_lzma(image);self.assertEqual(decoded,payload);self.assertEqual(info['stream_offset'],1024)
 def test_no_spi_table_is_unknown_not_pass(self):
  with self.assertRaises(ValueError):da.flash_table(b'BH25Q64\x68\x40\x17'+bytes(65536))
 def test_flash_struct_size(self):self.assertEqual(struct.calcsize('<I6sBxI4H'),24)
class SourceTests(unittest.TestCase):
 def test_dev_profile_added_once(self):
  src='DEVICE_VARS += IMAGE_SIZE\ndefine Device/RSD0614\nendef\n';once=hs.patch_image_makefile(src);self.assertEqual(hs.patch_image_makefile(once),once);self.assertIn('IMAGE_SIZE DEV_PROFILE',once)
 def test_missing_device_rejected(self):
  with self.assertRaises(ValueError):hs.patch_image_makefile('DEVICE_VARS += IMAGE_SIZE\n')
 def test_missing_export_anchor_rejected(self):
  with self.assertRaises(ValueError):hs.patch_image_makefile('define Device/RSD0614\nendef\n')
 def test_irq_diagnostic_mask_patch_idempotent(self):
  src='prefix\n'+hs.IRQ_UNSAFE_BLOCK+'\nsuffix\n';one=hs.patch_irq_source(src);self.assertEqual(hs.patch_irq_source(one),one);self.assertIn('ic_w32(0, REALTEK_IC_REG_MASK);',one);self.assertIn('REALTEK_IC_REG_STATUS',one);self.assertIn('return 0;',one);self.assertNotIn('// Return only MARK1',one)
 def test_done_script_never_mounts_persistent_root(self):
  done=hs.BASE_FILES['etc/init.d/done'];self.assertNotIn('mount_root',done);self.assertNotIn('/dev/mtd',done);self.assertNotIn('sysupgrade',done);self.assertIn('set_state done',done)
 def test_boot_script_removes_persistent_root_fallback(self):
  src='#!/bin/sh /etc/rc.common\nboot() {\n'+hs.BOOT_MOUNT_ROOT_LINE+'\t/sbin/kmodloader\n}\n';one=hs.patch_boot_script(src);self.assertEqual(hs.patch_boot_script(one),one);self.assertNotIn('mount_root',one);self.assertIn('kmodloader',one)
 def test_default_network_does_not_synthesize_eth_interfaces(self):
  src=". /lib/functions/uci-defaults.sh\nboard_config_update\n"+hs.DEFAULT_NETWORK_UNSAFE+"board_config_flush\n";one=hs.patch_default_network_script(src);self.assertEqual(hs.patch_default_network_script(one),one);self.assertNotIn("ucidef_set_interface_lan 'eth0'",one);self.assertNotIn('eth1',one);self.assertIn('board_config_flush',one)
 def test_kernel_config_idempotent(self):
  src='CONFIG_NET_RTL819X=y\nCONFIG_RTL8192CD=m\nCONFIG_SPI_SHEIPA=y\n';one=hs.patch_kernel_config(src);self.assertEqual(hs.patch_kernel_config(one),one);self.assertIn('CONFIG_SPI_SHEIPA=y',one)
  for key in hs.DISABLE_KERNEL:self.assertIn('# '+key+' is not set',one)
 def test_loopback_files_no_physical_operations(self):
  for body in hs.BASE_FILES.values():
   for forbidden in ('/dev/mtd','swconfig ','/sys/module/rtl819x','/proc/rtl865','192.168.'):self.assertNotIn(forbidden,body)
 def test_all_local_shell_fragments_parse(self):
  for name,body in hs.BASE_FILES.items():
   if body.startswith('#!'):
    p=subprocess.run(['sh','-n'],input=body,text=True,capture_output=True);self.assertEqual(p.returncode,0,(name,p.stderr))
 def test_make_late_global_reproduction_and_fix(self):
  prefix='DEV_PROFILE := RSD0614\n';suffix='DEV_PROFILE := ACTIONRF1200\nall:\n\t@printf "%s\\n" "$(DEV_PROFILE)"\n'
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'Makefile';p.write_text(prefix+suffix);old=subprocess.check_output(['make','-s','-C',td],text=True).strip();p.write_text(prefix+'all: DEV_PROFILE := $(DEV_PROFILE)\n'+suffix);new=subprocess.check_output(['make','-s','-C',td],text=True).strip();self.assertEqual(old,'ACTIONRF1200');self.assertEqual(new,'RSD0614')
 def test_nor_patch_applies_and_is_conservative(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'drivers/mtd/spi-nor/spi-nor.c';p.parent.mkdir(parents=True);p.write_text('/* bounded fixture using pinned upstream table context */\nstatic const struct flash_info spi_nor_ids[] = {\n\t/* Atmel -- some are (confusingly) marketed as "DataFlash" */\n\t{ "at25fs010",  INFO(0x1f6601, 0, 32 * 1024,   4, SECT_4K) },\n\t{ },\n};\n');run=subprocess.run(['patch','--batch','--fuzz=0','-p1','-i',str(ROOT/'patches'/hs.PATCH_NAME)],cwd=td,text=True,capture_output=True);self.assertEqual(run.returncode,0,run.stdout+run.stderr);t=p.read_text();self.assertIn('INFO(0x684017, 0, 64 * 1024, 128',t);self.assertIn('SPI_NOR_NO_FR | SPI_NOR_SKIP_SFDP',t);self.assertNotIn('SPI_NOR_QUAD_READ',t)
 def test_uart_register_fix_applies_after_full_diagnostic_stack(self):
  d=build_patched_dw8250().decode()
  for token in (
   '#include <linux/of_address.h>',
   'static u32 rtl8197f_read_soc_id(void)',
   'of_find_compatible_node(NULL, NULL, "realtek,rtl819x-sysc")',
   'unsigned int\t\tis_rtl8197f:1;',
   'static int rtl8197f_dl_read(',
   'static void rtl8197f_dl_write(',
   'static int rtl8197f_translate_lcr(struct dw8250_data *d, int value)',
   'unsigned int wlen = value & UART_LCR_WLEN8;',
   'value = (value & ~UART_LCR_WLEN8) | (wlen - 2);',
   'd->last_lcr = value;',
   'static void rtl8197f_diag_irq(',
   'if (!d->is_rtl8197f || d->diag_dumped)',
   'if (d->is_rtl8197f)',
   'bool is_non_vg = ((soc_id & 0xFFFFF000U) == 0x8197F000U);',
   'p->flags |= UPF_SKIP_TEST | UPF_FIXED_TYPE;',
   'data->tx_reg = 9;',
   'data->rx_reg = 9;',
   'data->adjlcr = true;',
   'data->tx_reg = UART_TX;',
   'data->rx_reg = UART_RX;',
   'data->adjlcr = false;',
   'up->dl_read = rtl8197f_dl_read;',
   'up->dl_write = rtl8197f_dl_write;',
   'rtl8197f-uart: soc_id=0x%08x mode=%s tx_reg=%u rx_reg=%u adjlcr=%u\\n',
  ):self.assertIn(token,d)
  for stale in ('p->flags = UPF_SKIP_TEST| UPF_FIXED_TYPE;','if(value == UART_LCR_WLEN7 || value == UART_LCR_WLEN8)','if (!d->adjlcr || d->diag_dumped)'):
   self.assertNotIn(stale,d)
  quirks=d[d.index('static void dw8250_quirks('):d.index('static void dw8250_setup_port(')]
  self.assertNotIn('fifosize',quirks)
 def test_rtl8197f_lcr_translated_before_mmio_write(self):
  d=build_patched_dw8250().decode()
  check_lcr=d[d.index('static void dw8250_check_lcr('):d.index('static int dw_change_offset(')]
  self.assertNotIn('adjlcr',check_lcr);self.assertNotIn('rtl8197f_translate_lcr',check_lcr);self.assertNotIn('last_lcr',check_lcr)
  for fn,end_anchor,mmio in (
   ('static void dw8250_serial_out(','static unsigned int dw8250_serial_in(','writeb(value,'),
   ('static void dw8250_serial_out32(','static unsigned int dw8250_serial_in32(','writel(value,'),
   ('static void dw8250_serial_out32be(','static unsigned int dw8250_serial_in32be(','iowrite32be(value,'),
  ):
   body=d[d.index(fn):d.index(end_anchor)]
   t_idx=body.index('value = rtl8197f_translate_lcr(d, value);');w_idx=body.index(mmio);c_idx=body.index('dw8250_check_lcr(p, value);')
   self.assertLess(t_idx,w_idx,fn);self.assertLess(w_idx,c_idx,fn)
 def test_rtl8197f_soc_id_dispatch_vg_vs_non_vg_c_simulation(self):
  dw_bytes=build_patched_dw8250()
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'drivers/tty/serial/8250').mkdir(parents=True);(root/'include/linux').mkdir(parents=True);(root/'include/asm').mkdir(parents=True)
   (root/'drivers/tty/serial/8250/8250_dw.c').write_bytes(dw_bytes)
   (root/'include/linux/serial_reg.h').write_bytes((ROOT/'fixtures/linux-4.14.187/include/uapi/linux/serial_reg.h').read_bytes())
   (root/'include/stub_common.h').write_text(DW8250_SIM_STUB_H)
   for hdr in ('linux/device.h','linux/io.h','linux/module.h','linux/serial_8250.h','linux/of.h','linux/of_address.h','linux/of_irq.h','linux/of_platform.h','linux/platform_device.h','linux/slab.h','linux/acpi.h','linux/clk.h','linux/reset.h','linux/pm_runtime.h','asm/byteorder.h'):
    (root/'include'/hdr).write_text('#include "stub_common.h"\n')
   (root/'drivers/tty/serial/8250/8250.h').write_text('#include "stub_common.h"\n')
   (root/'sim.c').write_text(DW8250_SIM_MAIN_C)
   cc=subprocess.run(['gcc','-std=gnu11','-O2','-DCONFIG_PM','-DCONFIG_PM_SLEEP','-Wall','-Wextra','-Wno-unused-function','-Wno-unused-parameter','-Wno-sign-compare','-Werror','-I',str(root/'include'),'-I',str(root),str(root/'sim.c'),'-o',str(root/'sim')],capture_output=True,text=True)
   self.assertEqual(cc.returncode,0,cc.stdout+cc.stderr)
   ex=subprocess.run([str(root/'sim')],capture_output=True,text=True)
   self.assertEqual(ex.returncode,0,ex.stdout+ex.stderr)
 def test_rtl8197f_lcr_translation_preserves_composite_bits(self):
  def translate(value):
   wlen=value & 0x03
   return ((value & ~0x03)|(wlen-2)) if wlen in (2,3) else value
  self.assertEqual(translate(0x13),0x11);self.assertEqual(translate(0x83),0x81);self.assertEqual(translate(0x0b),0x09);self.assertEqual(translate(0x01),0x01)
 def test_builder_v539_volume_separate(self):
  t=(ROOT/'Build-RSD0614.ps1').read_text(encoding='utf-8-sig');self.assertIn('rsd0614-openwrt-builder:v5.1',t);self.assertIn('rsd0614-openwrt-v539-work',t);self.assertIn("-ne 'v5.3.9'",t);self.assertIn('rsd0614.work=v5.3.9',t)
  for old_vol in ('rsd0614-openwrt-v538-work','rsd0614-openwrt-v537-work','rsd0614-openwrt-v532-work','rsd0614-openwrt-v53-work','rsd0614-openwrt-v52-work'):self.assertNotIn(old_vol,t)
  self.assertIn('if (-not $HaveBuilder -or $RebuildBuilder)',t);self.assertNotIn('volume rm',t);self.assertNotIn('volume prune',t)
  hv=json.loads((ROOT/'HOTFIX_VERSION.json').read_text());self.assertEqual(hv['volume'],'rsd0614-openwrt-v539-work');self.assertEqual(hv['volume_label'],'rsd0614.work=v5.3.9');self.assertIn('rsd0614-openwrt-v538-work',hv['preserve_old_volumes'])
 def test_builder_ps1_captures_image_id_before_recording_and_env(self):
  t=(ROOT/'Build-RSD0614.ps1').read_text(encoding='utf-8-sig')
  assign="$ImageId = (& docker image inspect $Image --format '{{.Id}}' | Out-String).Trim()"
  record='$ImageId | Set-Content -Encoding utf8 (Join-Path $Logs "$RunId-builder-image-id.txt")'
  env_arg='"BUILDER_IMAGE_ID=$ImageId"'
  self.assertIn(assign,t);self.assertIn(record,t);self.assertIn(env_arg,t)
  self.assertLess(t.index(assign),t.index(record));self.assertLess(t.index(record),t.index(env_arg))
 def test_build_prefetches_sources_before_parallel_compile(self):
  t=(ROOT/'build-rsd0614-initramfs.sh').read_text();download='STAGE=download; make download V=s';compile='STAGE=compile; make -j"$JOBS" V=s';self.assertIn(download,t);self.assertIn(compile,t);self.assertLess(t.index(download),t.index(compile))
 def test_deep_audit_runs_before_candidate_result(self):
  t=(ROOT/'build-rsd0614-initramfs.sh').read_text();self.assertLess(t.index('"$PORT_DIR/deep_audit.py"'),t.index("echo 'COMPILE=PASS'"));self.assertIn('export_build_evidence.py',t)
 def test_repo_manifest_matches_current_files(self):
  missing=[];mismatch=[]
  for line in (ROOT/'REPO_MANIFEST.sha256').read_text().splitlines():
   if not line.strip():continue
   digest,rel=line.split(None,1);rel=rel.strip();path=ROOT/rel
   if not path.is_file():missing.append(rel);continue
   actual=hashlib.sha256(path.read_bytes()).hexdigest()
   if actual!=digest:mismatch.append((rel,digest,actual))
  self.assertEqual(missing,[],f'missing manifest files: {missing}')
  self.assertEqual(mismatch,[],f'manifest hash drift: {mismatch}')
 def test_v539_metadata_and_provenance_wiring(self):
  lock=json.loads((ROOT/'SOURCE_LOCK.json').read_text());self.assertEqual(lock['bundle_version'],'5.3.9');self.assertEqual(lock['persistent_flash'],'NO-GO');self.assertFalse(lock['ram_boot_authorized']);self.assertIn('direct NET/PCIe/WiFi IRQs masked',lock['intent']);self.assertIn('all enabled auto mount_root paths suppressed',lock['intent']);self.assertIn('default eth0/eth1 synthesis suppressed',lock['intent']);self.assertIn('realtek,rtl819x-sysc SoC ID',lock['intent']);self.assertIn('RTL8197FH-VG (0x81970000)',lock['intent'])
  self.assertEqual(hs.BASE_FILES['etc/rsd0614-diagnostic-mode'],'v5.3.9-uart-soc-id-dispatch\n')
  self.assertIn("b'v5.3.9-uart-soc-id-dispatch\\n'",(ROOT/'deep_audit.py').read_text())
  build=(ROOT/'build-rsd0614-initramfs.sh').read_text();self.assertIn('PORT_INPUT_FINGERPRINT.txt',build);self.assertIn('--port-fingerprint',build);self.assertIn('--project-commit',build);self.assertIn('--builder-image-id',build)
  wrapper=(ROOT/'Build-RSD0614.ps1').read_text(encoding='utf-8-sig');self.assertIn('BUILDER_IMAGE_ID=',wrapper)
  workflow=(ROOT/'.github/workflows/build-initramfs.yml').read_text();self.assertIn('BUILDER_IMAGE_ID=',workflow);self.assertIn('PROJECT_COMMIT=$GITHUB_SHA',workflow)
class TreeTransactionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.tree=self.root/'openwrt';self.tree.mkdir();self.audit=self.root/'audit';target=self.tree/'target/linux/realtek';(target/'base-files/etc/init.d').mkdir(parents=True);(target/'base-files/etc/init.d/dir842-asic').write_text('fixture old script');(target/'image').mkdir();(target/'image/Makefile').write_text('DEVICE_VARS += IMAGE_SIZE\ndefine Device/RSD0614\nendef\n');(target/'rtl8197f').mkdir();(target/'rtl8197f/config-4.14').write_text('CONFIG_NET_RTL819X=y\n');irq=target/'files-4.14/arch/mips/realtek/irq.c';irq.parent.mkdir(parents=True);irq.write_text(hs.IRQ_UNSAFE_BLOCK+'\n');boot=self.tree/'package/base-files/files/etc/init.d/boot';boot.parent.mkdir(parents=True);boot.write_text('#!/bin/sh /etc/rc.common\nboot() {\n'+hs.BOOT_MOUNT_ROOT_LINE+'\t/sbin/kmodloader\n}\n');defaultnet=self.tree/'package/base-files/files/etc/board.d/99-default_network';defaultnet.parent.mkdir(parents=True);defaultnet.write_text('. /lib/functions/uci-defaults.sh\nboard_config_update\n'+hs.DEFAULT_NETWORK_UNSAFE+'board_config_flush\n')
  def git(*a):return subprocess.check_output(['git','-C',str(self.tree),*a],text=True,stderr=subprocess.DEVNULL).strip()
  git('init','-q');git('add','.');git('-c','user.name=Fixture','-c','user.email=test@example.invalid','commit','-qm','fixture');self.head=git('rev-parse','HEAD');self.target=target
 def tearDown(self):self.tmp.cleanup()
 def test_real_filesystem_isolation(self):
  result=hs.harden(self.tree,ROOT,self.audit,expected=self.head);self.assertEqual({r['path'] for r in hs.tree_records(self.target/'base-files')},set(hs.BASE_FILES));self.assertIn(hs.IRQ_SAFE_BLOCK,(self.target/'files-4.14/arch/mips/realtek/irq.c').read_text());self.assertNotIn('mount_root',(self.tree/'package/base-files/files/etc/init.d/boot').read_text());self.assertNotIn("ucidef_set_interface_lan 'eth0'",(self.tree/'package/base-files/files/etc/board.d/99-default_network').read_text());self.assertTrue((Path(result['retained_source_backup'])/'etc/init.d/dir842-asic').exists());self.assertFalse((self.target/'base-files/etc/init.d/dir842-asic').exists());self.assertEqual((self.target/'base-files').stat().st_mode&0o777,0o755);hs.harden(self.tree,ROOT,self.audit,expected=self.head);self.assertEqual({r['path'] for r in hs.tree_records(self.target/'base-files')},set(hs.BASE_FILES))
 def test_bad_revision_no_mutation(self):
  before=hs.tree_records(self.target)
  with self.assertRaises(ValueError):hs.harden(self.tree,ROOT,self.audit,expected='0'*40)
  self.assertEqual(hs.tree_records(self.target),before)
 def test_bad_anchor_no_mutation(self):
  (self.target/'image/Makefile').write_text('invalid');before=hs.tree_records(self.target)
  with self.assertRaises(ValueError):hs.harden(self.tree,ROOT,self.audit,expected=self.head)
  self.assertEqual(hs.tree_records(self.target),before)
 def test_bad_irq_anchor_no_mutation(self):
  irq=self.target/'files-4.14/arch/mips/realtek/irq.c';irq.write_text('unexpected irq source');before=hs.tree_records(self.tree)
  with self.assertRaises(ValueError):hs.harden(self.tree,ROOT,self.audit,expected=self.head)
  self.assertEqual(hs.tree_records(self.tree),before)
 def test_bad_boot_anchor_no_mutation(self):
  boot=self.tree/'package/base-files/files/etc/init.d/boot';boot.write_text('unexpected boot source');before=hs.tree_records(self.tree)
  with self.assertRaises(ValueError):hs.harden(self.tree,ROOT,self.audit,expected=self.head)
  self.assertEqual(hs.tree_records(self.tree),before)
 def test_bad_default_network_anchor_no_mutation(self):
  p=self.tree/'package/base-files/files/etc/board.d/99-default_network';p.write_text('unexpected default network source');before=hs.tree_records(self.tree)
  with self.assertRaises(ValueError):hs.harden(self.tree,ROOT,self.audit,expected=self.head)
  self.assertEqual(hs.tree_records(self.tree),before)
 def test_symlink_target_refused(self):
  original=self.target/'rtl8197f/config-4.14';original.unlink();external=self.root/'important';external.write_text('preserve');original.symlink_to(external)
  with self.assertRaises(ValueError):hs.harden(self.tree,ROOT,self.audit,expected=self.head)
  self.assertEqual(external.read_text(),'preserve')
 def test_backup_inside_source_refused(self):
  with self.assertRaises(ValueError):hs.harden(self.tree,ROOT,self.tree/'audit',expected=self.head)
class ExportEvidenceTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.patched_dw8250=build_patched_dw8250()
  cls.serial_reg_bytes=(ROOT/'fixtures/linux-4.14.187/include/uapi/linux/serial_reg.h').read_bytes()
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.tree=self.root/'tree';self.out=self.root/'out';self.linux=self.tree/'build_dir/target-mipsel_24kc_musl/linux-realtek_rtl8197f/linux-4.14.187';self.linux.mkdir(parents=True);(self.linux/'.config').write_text('CONFIG_MTD_SPI_NOR=y\nCONFIG_SPI_SHEIPA=y\nCONFIG_SOC_RTL8197F=y\nCONFIG_SERIAL_8250=y\nCONFIG_SERIAL_8250_CONSOLE=y\nCONFIG_SERIAL_8250_DW=y\n')
  for n in ('System.map','vmlinux'):(self.linux/n).write_text('explicit fixture')
  for n in ('vmlinux-initramfs.elf','vmlinux-initramfs.debug'):(self.linux.parent/n).write_text('explicit fixture')
  src=self.linux/'drivers/mtd/spi-nor/spi-nor.c';src.parent.mkdir(parents=True);src.write_text('{ "bh25q64", INFO(0x684017, 0, 65536, 128, 0x2008) },');irq=self.linux/'arch/mips/realtek/irq.c';irq.parent.mkdir(parents=True);irq.write_text(hs.IRQ_SAFE_BLOCK+'\n');uart=self.linux/'include/uapi/linux/serial_reg.h';uart.parent.mkdir(parents=True);uart.write_bytes(self.serial_reg_bytes);dw=self.linux/'drivers/tty/serial/8250/8250_dw.c';dw.parent.mkdir(parents=True);dw.write_bytes(self.patched_dw8250);self.log=self.root/'build.log';self.log.write_text('BOARD="RSD0614" SUBTARGET="rtl8197f"\n')
 def tearDown(self):self.tmp.cleanup()
 def test_export_only_records_fixture_not_boot_success(self):
  from export_build_evidence import export;export(self.tree,self.out,self.log);manifest=json.loads((self.out/'kernel-evidence/manifest.json').read_text());self.assertEqual(len(manifest['files']),9);self.assertEqual(manifest['loader_board_values'],['RSD0614'])
 def test_export_records_provenance(self):
  from export_build_evidence import export;export(self.tree,self.out,self.log,port_fingerprint='a'*64,project_commit='b'*40,builder_image_id='sha256:'+'c'*64);manifest=json.loads((self.out/'kernel-evidence/manifest.json').read_text());self.assertEqual(manifest['provenance'],{'port_input_fingerprint':'a'*64,'project_commit':'b'*40,'builder_image_id':'sha256:'+'c'*64})
 def test_wrong_board_rejected(self):
  from export_build_evidence import export;self.log.write_text('BOARD="ACTIONRF1200" SUBTARGET="rtl8197f"\n')
  with self.assertRaises(ValueError):export(self.tree,self.out,self.log)
 def test_missing_board_log_rejected(self):
  from export_build_evidence import export;self.log.write_text('no loader evidence')
  with self.assertRaises(ValueError):export(self.tree,self.out,self.log)
 def test_driver_survived_config_rejected(self):
  from export_build_evidence import export
  with (self.linux/'.config').open('a') as f:f.write('CONFIG_NET_RTL819X=y\n')
  with self.assertRaises(ValueError):export(self.tree,self.out,self.log)
 def test_missing_spi_patch_rejected(self):
  from export_build_evidence import export;(self.linux/'drivers/mtd/spi-nor/spi-nor.c').write_text('not patched')
  with self.assertRaises(ValueError):export(self.tree,self.out,self.log)
 def test_modified_generic_serial_reg_rejected(self):
  from export_build_evidence import export;(self.linux/'include/uapi/linux/serial_reg.h').write_text('#define UART_RX 9\n#define UART_TX 9\n#define UART_IIR_ID 0x0e\n#define UART_LCR_WLEN7 0x00\n#define UART_LCR_WLEN8 0x01\n')
  with self.assertRaises(ValueError):export(self.tree,self.out,self.log)
 def test_missing_base_0004_uart_semantics_rejected(self):
  from export_build_evidence import export;(self.linux/'drivers/tty/serial/8250/8250_dw.c').write_text('generic dw8250 only')
  with self.assertRaises(ValueError):export(self.tree,self.out,self.log)
 def test_missing_dw8250_busy_recovery_rejected(self):
  from export_build_evidence import export;(self.linux/'drivers/tty/serial/8250/8250_dw.c').write_text('of_device_is_compatible(np, "realtek,rtl8197f-uart")\ndata->tx_reg = 9;\ndata->rx_reg = 9;\ndata->adjlcr = true;\nvalue -= 2;\np->type = PORT_16550A;\ndata->skip_autocfg = true;\n')
  with self.assertRaises(ValueError):export(self.tree,self.out,self.log)
 def test_missing_uart_irq_cause_diagnostic_rejected(self):
  from export_build_evidence import export
  p=self.linux/'drivers/tty/serial/8250/8250_dw.c';p.write_text(p.read_text().replace('static void rtl8197f_diag_irq(','static void removed_diag_irq('))
  with self.assertRaises(ValueError):export(self.tree,self.out,self.log)
 def test_missing_rtl8197f_divisor_callbacks_rejected(self):
  from export_build_evidence import export
  p=self.linux/'drivers/tty/serial/8250/8250_dw.c';p.write_text(p.read_text().replace('up->dl_read = rtl8197f_dl_read;',''))
  with self.assertRaises(ValueError):export(self.tree,self.out,self.log)
 def test_missing_soc_id_dispatch_rejected(self):
  from export_build_evidence import export
  p=self.linux/'drivers/tty/serial/8250/8250_dw.c';p.write_text(p.read_text().replace('bool is_non_vg = ((soc_id & 0xFFFFF000U) == 0x8197F000U);',''))
  with self.assertRaises(ValueError):export(self.tree,self.out,self.log)
 def test_missing_prewrite_lcr_translation_rejected(self):
  from export_build_evidence import export
  p=self.linux/'drivers/tty/serial/8250/8250_dw.c';p.write_text(p.read_text().replace('value = rtl8197f_translate_lcr(d, value);','',1))
  with self.assertRaises(ValueError):export(self.tree,self.out,self.log)
 def test_stale_flags_clobber_rejected(self):
  from export_build_evidence import export
  p=self.linux/'drivers/tty/serial/8250/8250_dw.c';p.write_text(p.read_text()+'\np->flags = UPF_SKIP_TEST| UPF_FIXED_TYPE;\n')
  with self.assertRaises(ValueError):export(self.tree,self.out,self.log)
 def test_stale_whole_value_lcr_adjustment_rejected(self):
  from export_build_evidence import export
  self.assertNotIn("'value -= 2;'",(ROOT/'export_build_evidence.py').read_text())
  p=self.linux/'drivers/tty/serial/8250/8250_dw.c';p.write_text(p.read_text()+'\nif(value == UART_LCR_WLEN7 || value == UART_LCR_WLEN8){}\n')
  with self.assertRaises(ValueError):export(self.tree,self.out,self.log)
 def test_stale_adjlcr_diag_guard_rejected(self):
  from export_build_evidence import export
  p=self.linux/'drivers/tty/serial/8250/8250_dw.c';p.write_text(p.read_text()+'\nif (!d->adjlcr || d->diag_dumped) return;\n')
  with self.assertRaises(ValueError):export(self.tree,self.out,self.log)
 def test_missing_irq_hardening_rejected(self):
  from export_build_evidence import export;(self.linux/'arch/mips/realtek/irq.c').write_text(hs.IRQ_UNSAFE_BLOCK+'\n')
  with self.assertRaises(ValueError):export(self.tree,self.out,self.log)
 def test_missing_required_elf_rejected(self):
  from export_build_evidence import export;(self.linux.parent/'vmlinux-initramfs.elf').unlink()
  with self.assertRaises(ValueError):export(self.tree,self.out,self.log)
if __name__=='__main__':unittest.main(verbosity=2)
