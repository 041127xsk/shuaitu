"""深入分析 writev + 尝试找到数据接收路径"""
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

var fcntl = new NativeFunction(findExport(findModule("libc.so"), "fcntl"), 'int', ['int', 'int', 'int']);
var F_GETFL = 3;
var O_ACCMODE = 3;

function getFdType(fd) {
    try {
        var flags = fcntl(fd, F_GETFL, 0);
        if (flags < 0) return "closed/invalid";
        // socket 的 flags 通常包含 O_RDWR 且不是普通文件
        // 更准确的判断：尝试 getsockopt
        return "fd=" + fd + " flags=" + flags;
    } catch(e) {
        return "error";
    }
}

var writevHit = 0;
var readHit = 0;

// Hook writev - 详细记录
(function() {
    var exp = findExport(findModule("libc.so"), "writev");
    if (!exp) return;
    Interceptor.attach(exp.address, {
        onEnter: function(args) {
            writevHit++;
            var fd = args[0].toInt32();
            var iovcnt = args[2].toInt32();
            var fdInfo = getFdType(fd);
            
            // 读取第一个 iov 的数据
            var iov = args[1];
            var base = Memory.readPointer(iov);
            var len = Memory.readU64(iov.add(Process.pointerSize)).toNumber();
            
            if (len > 0 && len < 4096) {
                var data = Memory.readByteArray(base, Math.min(len, 256));
                send({type: 'writev', fd: fd, fdInfo: fdInfo, iovcnt: iovcnt, len: len, total: writevHit}, data);
            }
        }
    });
    send({type: 'info', msg: 'writev() hooked'});
})();

// Hook read - 详细记录（包括 read 返回 0/-1 的情况）
(function() {
    var exp = findExport(findModule("libc.so"), "read");
    if (!exp) return;
    Interceptor.attach(exp.address, {
        onEnter: function(args) {
            this.fd = args[0].toInt32();
            this.buf = args[1];
            this.count = args[2].toInt32();
        },
        onLeave: function(retval) {
            readHit++;
            var ret = retval.toInt32();
            var fdInfo = getFdType(this.fd);
            
            if (ret > 0 && ret < 4096 && this.buf) {
                var data = Memory.readByteArray(this.buf, Math.min(ret, 256));
                send({type: 'read', fd: this.fd, fdInfo: fdInfo, len: ret, ret: ret, total: readHit}, data);
            } else if (ret <= 0 && (readHit % 100 === 1)) {
                send({type: 'read_empty', fd: this.fd, fdInfo: fdInfo, ret: ret, total: readHit});
            }
        }
    });
    send({type: 'info', msg: 'read() hooked (verbose)'});
})();

// Hook syscall - 直接系统调用可能绕过 libc
(function() {
    var exp = findExport(findModule("libc.so"), "syscall");
    if (!exp) return;
    Interceptor.attach(exp.address, {
        onEnter: function(args) {
            var num = args[0].toInt32();
            // x86_64 Linux syscall numbers: read=0, write=1, readv=19, writev=20, recvfrom=45, sendto=44
            if (num === 0 || num === 1 || num === 19 || num === 20 || num === 44 || num === 45) {
                send({type: 'syscall', num: num, name: (num===0?'read':num===1?'write':num===19?'readv':num===20?'writev':num===44?'sendto':'recvfrom')});
            }
        }
    });
    send({type: 'info', msg: 'syscall() hooked'});
})();

send({type: 'ready', msg: 'Monitoring writev + read + syscall. Please operate now.'});
'''

script = session.create_script(FRIDA_JS)

writev_count = 0
read_count = 0
syscall_hits = {}

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
        print(f"[{ts}] [WRITEV #{p['total']}] fd={p['fd']} {p['fdInfo']} iovcnt={p['iovcnt']} len={p['len']} | {preview}")

    elif t == 'read':
        read_count += 1
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        preview = ""
        if data:
            try:
                preview = data.decode('utf-8', errors='ignore')[:60].replace('\n', ' ')
            except:
                preview = data[:30].hex()
        print(f"[{ts}] [READ #{p['total']}] fd={p['fd']} {p['fdInfo']} len={p['len']} | {preview}")

    elif t == 'read_empty':
        read_count += 1
        if p['total'] % 500 == 1:
            print(f"[READ #{p['total']}] fd={p['fd']} ret={p['ret']} (empty/eagain)")

    elif t == 'syscall':
        name = p['name']
        syscall_hits[name] = syscall_hits.get(name, 0) + 1
        if syscall_hits[name] <= 5:
            print(f"[SYSCALL] {name} (num={p['num']})")

    elif t == 'info':
        print(f"[INFO] {p['msg']}")

script.on('message', on_message)
script.load()

print("[OK] 深入监控已启动。请在模拟器上操作（点击战报详情/刷新/翻页）")
print("[INFO] 监控 15 秒...\n")

try:
    time.sleep(15)
except KeyboardInterrupt:
    pass

session.detach()

print(f"\n===== 结果 =====")
print(f"writev: {writev_count} 次")
print(f"read:   {read_count} 次")
print(f"syscall: {syscall_hits}")
