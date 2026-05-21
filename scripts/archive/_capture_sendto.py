"""专门抓取 sendto/recvfrom/writev 数据"""
import frida, time
from datetime import datetime

pid = 4568
device = frida.get_usb_device(timeout=5)
session = device.attach(pid)

FRIDA_JS = '''
var hitCount = {};

function hookSendto() {
    var libc = Process.findModuleByName("libc.so");
    var exports = libc.enumerateExports();
    var found = exports.find(function(e) { return e.name === 'sendto'; });
    if (!found) return;
    
    Interceptor.attach(found.address, {
        onEnter: function(args) {
            var fd = args[0].toInt32();
            var len = args[2].toInt32();
            hitCount['sendto'] = (hitCount['sendto'] || 0) + 1;
            if (len > 0 && len < 65536) {
                var data = Memory.readByteArray(args[1], Math.min(len, 1024));
                send({type: 'sendto', fd: fd, len: len}, data);
            }
        }
    });
    send({type: 'info', msg: 'sendto hooked'});
}

function hookRecvfrom() {
    var libc = Process.findModuleByName("libc.so");
    var exports = libc.enumerateExports();
    var found = exports.find(function(e) { return e.name === 'recvfrom'; });
    if (!found) return;
    
    Interceptor.attach(found.address, {
        onEnter: function(args) {
            this.buf = args[1];
            this.len = args[2].toInt32();
        },
        onLeave: function(retval) {
            var ret = retval.toInt32();
            hitCount['recvfrom'] = (hitCount['recvfrom'] || 0) + 1;
            if (ret > 0 && ret < 65536 && this.buf) {
                var data = Memory.readByteArray(this.buf, Math.min(ret, 1024));
                send({type: 'recvfrom', len: ret}, data);
            }
        }
    });
    send({type: 'info', msg: 'recvfrom hooked'});
}

function hookWritev() {
    var libc = Process.findModuleByName("libc.so");
    var exports = libc.enumerateExports();
    var found = exports.find(function(e) { return e.name === 'writev'; });
    if (!found) return;
    
    Interceptor.attach(found.address, {
        onEnter: function(args) {
            var fd = args[0].toInt32();
            var iovcnt = args[2].toInt32();
            hitCount['writev'] = (hitCount['writev'] || 0) + 1;
            
            var iov = args[1];
            var base = Memory.readPointer(iov);
            var len = Memory.readU64(iov.add(Process.pointerSize)).toNumber();
            
            if (len > 0 && len < 65536) {
                var data = Memory.readByteArray(base, Math.min(len, 1024));
                send({type: 'writev', fd: fd, iovcnt: iovcnt, len: len}, data);
            }
        }
    });
    send({type: 'info', msg: 'writev hooked'});
}

function hookSendmsg() {
    var libc = Process.findModuleByName("libc.so");
    var exports = libc.enumerateExports();
    var found = exports.find(function(e) { return e.name === 'sendmsg'; });
    if (!found) return;
    
    Interceptor.attach(found.address, {
        onEnter: function(args) {
            hitCount['sendmsg'] = (hitCount['sendmsg'] || 0) + 1;
            send({type: 'sendmsg', fd: args[0].toInt32()});
        }
    });
    send({type: 'info', msg: 'sendmsg hooked'});
}

hookSendto();
hookRecvfrom();
hookWritev();
hookSendmsg();

send({type: 'ready', msg: 'Active. Please operate emulator.'});
'''

script = session.create_script(FRIDA_JS)

stats = {'sendto': 0, 'recvfrom': 0, 'writev': 0, 'sendmsg': 0}

def on_message(msg, data):
    if msg['type'] != 'send':
        return
    p = msg['payload']
    t = p.get('type')

    if t in stats:
        stats[t] += 1

    if t in ('sendto', 'recvfrom', 'writev') and data:
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        try:
            # 尝试多种解码
            preview = None
            for enc in ['utf-8', 'gbk', 'latin-1']:
                try:
                    preview = data.decode(enc, errors='ignore')[:120].replace('\n', ' ').replace('\r', '')
                    if preview.strip():
                        break
                except:
                    pass
            if not preview or not preview.strip():
                preview = data[:60].hex()
            
            fd_info = f" fd={p.get('fd', 'N/A')}" if 'fd' in p else ''
            print(f"[{ts}] [{t.upper():8}]{fd_info} {p.get('len', 0)}b | {preview}")
        except Exception as e:
            print(f"[{ts}] [{t.upper()}] decode error: {e}")

    elif t == 'sendmsg':
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{ts}] [SENDMSG] fd={p.get('fd')}")

    elif t == 'info':
        print(f"[INFO] {p['msg']}")

script.on('message', on_message)
script.load()

print("[OK] sendto/recvfrom/writev/sendmsg 监控已启动")
print("[INFO] 请在模拟器上操作（建议：点击刷新按钮、切换战报类型、点击详情）")
print("[INFO] 监控 30 秒...\n")

try:
    time.sleep(30)
except KeyboardInterrupt:
    pass

session.detach()

print(f"\n===== 统计 =====")
for k, v in stats.items():
    print(f"  {k}: {v} 次")
