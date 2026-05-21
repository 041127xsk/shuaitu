"""深入分析 writev + read - 修复版"""
import frida, time
from datetime import datetime

pid = 4568
device = frida.get_usb_device(timeout=5)
session = device.attach(pid)

FRIDA_JS = '''
function findModule(name) {
    var m = Process.findModuleByName(name);
    if (m) return m;
    var mods = Process.enumerateModules();
    return mods.find(function(mod) { return mod.name.indexOf(name) !== -1; });
}

function findExport(mod, name) {
    if (!mod) return null;
    var exports = mod.enumerateExports();
    return exports.find(function(e) { return e.name === name; });
}

var libc = findModule("libc.so");
var writevHit = 0;
var readHit = 0;

// Hook writev
var writevExp = findExport(libc, "writev");
if (writevExp) {
    Interceptor.attach(writevExp.address, {
        onEnter: function(args) {
            writevHit++;
            var fd = args[0].toInt32();
            var iovcnt = args[2].toInt32();
            var iov = args[1];
            var base = Memory.readPointer(iov);
            var len = Memory.readU64(iov.add(Process.pointerSize)).toNumber();
            
            if (len > 0 && len < 8192) {
                var data = Memory.readByteArray(base, Math.min(len, 256));
                send({type: 'writev', fd: fd, iovcnt: iovcnt, len: len, total: writevHit}, data);
            }
        }
    });
    send({type: 'info', msg: 'writev hooked'});
} else {
    send({type: 'error', msg: 'writev not found'});
}

// Hook read
var readExp = findExport(libc, "read");
if (readExp) {
    Interceptor.attach(readExp.address, {
        onEnter: function(args) {
            this.fd = args[0].toInt32();
            this.buf = args[1];
            this.count = args[2].toInt32();
        },
        onLeave: function(retval) {
            readHit++;
            var ret = retval.toInt32();
            if (ret > 0 && ret < 8192 && this.buf) {
                var data = Memory.readByteArray(this.buf, Math.min(ret, 256));
                send({type: 'read', fd: this.fd, len: ret, total: readHit}, data);
            } else if (ret <= 0) {
                send({type: 'read_empty', fd: this.fd, ret: ret, total: readHit});
            }
        }
    });
    send({type: 'info', msg: 'read hooked'});
} else {
    send({type: 'error', msg: 'read not found'});
}

send({type: 'ready', msg: 'Active. Please operate emulator.'});
'''

script = session.create_script(FRIDA_JS)

writev_count = 0
read_count = 0

def on_message(msg, data):
    global writev_count, read_count
    if msg['type'] != 'send':
        return
    p = msg['payload']
    t = p.get('type')

    if t == 'writev':
        writev_count += 1
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        preview = ""
        if data:
            try:
                preview = data.decode('utf-8', errors='ignore')[:60].replace('\n', ' ')
                if not preview.strip():
                    preview = data[:30].hex()
            except:
                preview = data[:30].hex()
        print(f"[{ts}] [WRITEV #{p['total']}] fd={p['fd']} len={p['len']} | {preview}")

    elif t == 'read':
        read_count += 1
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        preview = ""
        if data:
            try:
                preview = data.decode('utf-8', errors='ignore')[:60].replace('\n', ' ')
            except:
                preview = data[:30].hex()
        print(f"[{ts}] [READ #{p['total']}] fd={p['fd']} len={p['len']} | {preview}")

    elif t == 'read_empty':
        read_count += 1
        if p['total'] % 200 == 1:
            print(f"[READ #{p['total']}] fd={p['fd']} ret={p['ret']} (empty)")

    elif t in ('info', 'error'):
        print(f"[{t.upper()}] {p['msg']}")

script.on('message', on_message)
script.load()

print("[OK] 监控已启动。请在模拟器上操作（点击详情/刷新/翻页）")
print("[INFO] 监控 15 秒...\n")

try:
    time.sleep(15)
except KeyboardInterrupt:
    pass

session.detach()

print(f"\n===== 结果 =====")
print(f"writev: {writev_count} 次")
print(f"read:   {read_count} 次")
