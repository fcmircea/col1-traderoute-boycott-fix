# Read-watchpoint on the fur word. Logs every READER instruction (IP + code).
# The unload handler reads the fur stock (mov ax,[bx+si+0x9a]) at file 0x2a80e/0x2a870
# just before depositing; if those readers appear in the broken case, the handler
# was ENTERED but skipped the write (=> caller-flag bug). Env WWATCH.
import gdb, os, time
LOG=open('/tmp/hits.log','a',buffering=1)
def log(s): LOG.write(s+'\n')
gdb.execute('set confirm off'); gdb.execute('set pagination off')
gdb.execute('set architecture i8086'); gdb.execute('target remote 127.0.0.1:1234')
addr=int(os.environ['WWATCH'],16)
gdb.execute(f'rwatch *(short *)0x{addr:x}')
log(f'ARMED rwatch=0x{addr:x}')
def r(n): return int(gdb.parse_and_eval('$'+n))&0xffffffff
inf=gdb.selected_inferior()
t0=time.time(); DEAD=t0+float(os.environ.get('GDB_SECONDS','230'))
seen={}
for i in range(20000):
    if time.time()>DEAD: log('DEADLINE'); break
    try: gdb.execute('continue',to_string=True)
    except gdb.error as e: log(f'CONTINUE-ERR {e}'); break
    cs,eip=r('cs')&0xffff,r('eip')&0xffff
    try: code=bytes(inf.read_memory((cs<<4)+eip-16,20)).hex()
    except Exception: code='??'
    key=eip
    seen[key]=seen.get(key,0)+1
    if seen[key]<=3:
        log(f'READ IP={eip:04x} CS={cs:04x} code@-16={code}')
log('SUMMARY '+' '.join(f'{k:04x}:{v}' for k,v in sorted(seen.items())))
log('GDB-DONE')
try: gdb.execute('detach')
except Exception: pass
