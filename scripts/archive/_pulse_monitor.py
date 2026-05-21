"""脉冲式监控 - 每 2 秒报告各函数调用次数"""
import frida, time
from datetime import datetime

pid = 4568
device = frida.get_usb_device(timeout=5)
session = device.attach(pid)

FRIDA_JS = '''
var hits = {};

function hook(name) {
    var libc = Process.findModuleByName("libc.so");
    if (!libc) return;
    var exports = libc.enumerateExports();
    var found = exports.find(function(e) { return e.name === name; });
    if (!found) {
        send({type: 'error', msg: name + ' not found'});
        return;
    }
    hits[name] = 0;
    Interceptor.attach(found.address, {
        onEnter: function(args) {
            hits[name] = (hits[name] || 0) + 1;
        }
    });
    send({type: 'info', msg: name + ' hooked'});
}

['send', 'sendto', 'sendmsg', 'recv', 'recvfrom', 'recvmsg',
 'read', 'write', 'readv', 'writev', 'pread', 'pwrite',
 'connect', 'epoll_wait'].forEach(hook);

// 每 2 秒报告一次
setInterval(function() {
    send({type: 'pulse', hits: hits});
}, 2000);

send({type: 'ready', msg: 'Pulse monitor active'});
'''

script = session.create_script(FRIDA_JS)

last_hits = {}

def on_message(msg, data):
    if msg['type'] != 'send':
        return
    p = msg['payload']
    if p.get('type') == 'pulse':
        ts = datetime.now().strftime("%H:%M:%S")
        current = p['hits']
        deltas = []
        for k, v in current.items():
            delta = v - last_hits.get(k, 0)
            if delta > 0:
                deltas.append(f"{k}={v}(+{delta})")
            elif v > 0:
                deltas.append(f"{k}={v}")
        if deltas:
            print(f"[{ts}] {' | '.join(deltas)}")
        else:
            print(f"[{ts}] (no activity)")
        last_hits.update(current)
    elif p.get('type') == 'info':
        print(f"[INFO] {p['msg']}")
    elif p.get('type') == 'error':
        print(f"[ERROR] {p['msg']}")

script.on('message', on_message)
script.load()

print("[OK] 脉冲监控已启动。请在模拟器上操作，观察计数变化。")
print("[INFO] 监控 30 秒... 按 Ctrl+C 提前停止\n")

try:
    time.sleep(30)
except KeyboardInterrupt:
    pass

session.detach()
print("\n[OK] 监控结束")
