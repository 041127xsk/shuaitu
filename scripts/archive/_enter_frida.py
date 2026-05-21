"""监控进入战报页面时的网络活动 - 简化版"""
import frida, time
from datetime import datetime

pid = 4568
device = frida.get_usb_device(timeout=5)
session = device.attach(pid)

FRIDA_JS = '''
var hits = {};
['send', 'sendto', 'sendmsg', 'recv', 'recvfrom', 'recvmsg', 'write', 'writev', 'connect'].forEach(function(name) {
    var libc = Process.findModuleByName("libc.so");
    if (!libc) return;
    var found = libc.enumerateExports().find(function(e) { return e.name === name; });
    if (!found) return;
    hits[name] = 0;
    Interceptor.attach(found.address, {
        onEnter: function(args) {
            hits[name] = (hits[name] || 0) + 1;
        }
    });
});

// SSL
var ssl = Process.findModuleByName("libssl.so");
if (ssl) {
    var exports = ssl.enumerateExports();
    var w = exports.find(function(e) { return e.name === 'SSL_write'; });
    var r = exports.find(function(e) { return e.name === 'SSL_read'; });
    if (w) { hits['ssl_write'] = 0; Interceptor.attach(w.address, { onEnter: function() { hits['ssl_write']++; } }); }
    if (r) { hits['ssl_read'] = 0; Interceptor.attach(r.address, { onEnter: function() { hits['ssl_read']++; } }); }
}

setInterval(function() {
    send({type: 'pulse', hits: hits});
}, 1000);

send({type: 'ready', msg: 'Active'});
'''

script = session.create_script(FRIDA_JS)
last_hits = {}

print("[OK] 监控已启动。请在模拟器上点击'同盟战报'进入页面！")
print("[INFO] 监控 15 秒...\n")

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
        if deltas:
            print(f"[{ts}] {' | '.join(deltas)}")
        last_hits.update(current)

script.on('message', on_message)
script.load()

try:
    time.sleep(15)
except KeyboardInterrupt:
    pass

session.detach()
print("\n[OK] 完成")
