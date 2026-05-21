"""专门抓取 sendmsg 数据，解析目标地址和内容"""
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

var libc = findModule("libc.so");
var exports = libc.enumerateExports();
var sendmsgAddr = exports.find(function(e) { return e.name === 'sendmsg'; });

if (!sendmsgAddr) {
    send({type: 'error', msg: 'sendmsg not found'});
} else {
    Interceptor.attach(sendmsgAddr.address, {
        onEnter: function(args) {
            var fd = args[0].toInt32();
            var msg = args[1];
            
            // x86_64 msghdr: name(8) namelen(4 pad4) iov(8) iovlen(8) control(8) controllen(8) flags(4)
            var namePtr = Memory.readPointer(msg);
            var nameLen = Memory.readU32(msg.add(8));
            var iovPtr = Memory.readPointer(msg.add(16));
            var iovLen = Memory.readU64(msg.add(24)).toNumber();
            
            var addr = null;
            if (!namePtr.isNull() && nameLen >= 16) {
                var family = Memory.readU16(namePtr);
                if (family === 2) { // AF_INET
                    var port = Memory.readU16(namePtr.add(2));
                    port = ((port & 0xFF) << 8) | ((port >> 8) & 0xFF);
                    var ip = [];
                    for (var i = 0; i < 4; i++) ip.push(Memory.readU8(namePtr.add(4 + i)));
                    addr = ip.join('.') + ':' + port;
                }
            }
            
            // 读取第一个 iov 的数据
            var dataLen = 0;
            var data = null;
            if (!iovPtr.isNull() && iovLen > 0) {
                var base = Memory.readPointer(iovPtr);
                dataLen = Memory.readU64(iovPtr.add(Process.pointerSize)).toNumber();
                if (dataLen > 0 && dataLen < 65536) {
                    data = Memory.readByteArray(base, Math.min(dataLen, 2048));
                }
            }
            
            send({type: 'sendmsg', fd: fd, addr: addr, dataLen: dataLen}, data);
        }
    });
    send({type: 'info', msg: 'sendmsg hooked'});
}

send({type: 'ready', msg: 'Active'});
'''

script = session.create_script(FRIDA_JS)

def on_message(msg, data):
    if msg['type'] != 'send':
        return
    p = msg['payload']
    if p.get('type') == 'sendmsg':
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        addr = p.get('addr') or 'unknown'
        dlen = p.get('dataLen', 0)
        preview = ""
        if data:
            try:
                preview = data.decode('utf-8', errors='ignore')[:120].replace('\n', ' ').replace('\r', '')
                if not preview.strip():
                    preview = data[:60].hex()
            except:
                preview = data[:60].hex()
        print(f"[{ts}] [SENDMSG] fd={p['fd']} -> {addr} len={dlen} | {preview}")
    elif p.get('type') == 'info':
        print(f"[INFO] {p['msg']}")
    elif p.get('type') == 'error':
        print(f"[ERROR] {p['msg']}")

script.on('message', on_message)
script.load()

print("[OK] sendmsg 深度监控已启动")
print("[INFO] 请在模拟器上操作，特别关注：")
print("      1. 点击刷新按钮")
print("      2. 切换战报类型（个人/同盟/州）")
print("      3. 点击某条战报详情")
print("      4. 翻页到列表底部\n")
print("[INFO] 监控 45 秒...\n")

try:
    time.sleep(45)
except KeyboardInterrupt:
    pass

session.detach()
print("\n[OK] 监控结束")
