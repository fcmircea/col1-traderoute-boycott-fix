# Write-watchpoint on Fort Orange's fur word (env WWATCH, hex linear).
# Logs every write: CS:IP (the writer instruction), new value, regs, stack.
import gdb, os, time
LOG = open('/tmp/hits.log','a',buffering=1)
def log(s): LOG.write(s+'\n')
gdb.execute('set confirm off'); gdb.execute('set pagination off')
gdb.execute('set architecture i8086')
gdb.execute('target remote 127.0.0.1:1234')
addr = int(os.environ['WWATCH'],16)
gdb.execute(f'watch *(short *)0x{addr:x}')   # write watchpoint
log(f'ARMED wwatch=0x{addr:x}')
def r(n): return int(gdb.parse_and_eval('$'+n)) & 0xffffffff
inf = gdb.selected_inferior()
t0=time.time(); DEADLINE=t0+float(os.environ.get('GDB_SECONDS','230'))
for i in range(8000):
    if time.time()>DEADLINE: log('DEADLINE'); break
    try: gdb.execute('continue',to_string=True)
    except gdb.error as e: log(f'CONTINUE-ERR {e}'); break
    try:
        cs,eip=r('cs')&0xffff,r('eip')&0xffff
        ss,esp=r('ss')&0xffff,r('esp')&0xffff
        ds=r('ds')&0xffff
        ax,bx,cx,dx=r('eax')&0xffff,r('ebx')&0xffff,r('ecx')&0xffff,r('edx')&0xffff
        si,di,bp=r('esi')&0xffff,r('edi')&0xffff,r('ebp')&0xffff
        lin=(cs<<4)+eip
        try: nv=int.from_bytes(bytes(inf.read_memory(addr,2)),'little')
        except Exception: nv=-1
        try: stack=bytes(inf.read_memory((ss<<4)+esp,48)).hex()
        except Exception: stack='??'
        try: code=bytes(inf.read_memory(lin-16,48)).hex()
        except Exception: code='??'
        log(f'HIT {i} t={time.time()-t0:.1f} CS={cs:04x} IP={eip:04x} LIN={lin:05x} '
            f'DS={ds:04x} newFUR={nv} AX={ax:04x} BX={bx:04x} CX={cx:04x} DX={dx:04x} '
            f'SI={si:04x} DI={di:04x} BP={bp:04x} SS:SP={ss:04x}:{esp:04x} CODE={code} STACK={stack}')
    except Exception as e:
        log(f'LOG-ERR {i} {e}')
log('GDB-DONE')
try: gdb.execute('detach')
except Exception: pass
