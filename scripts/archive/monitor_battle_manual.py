"""
手动操作网络监控
================
Frida 实时监控游戏进程的 send/recv，你手动点击/刷新/翻页，看哪个操作触发网络请求。

用法:
    py scripts/monitor_battle_manual.py
    # 然后你在模拟器上操作，按 Ctrl+C 停止
"""
import time
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "captures"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

GAME_PID = 3207

FRIDA_JS = '''
var TAG = "[MONITOR]";

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

// Hook send
(function() {
    var libc = findModule("libc.so");
    if (!libc) return;
    var s = findExport(libc, 'send');
    if (!s) return;
    Interceptor.attach(s.address, {
        onEnter: function(args) {
            var len = args[2].toInt32();
            if (len > 0 && len < 65536) {
                var data = Memory.readByteArray(args[1], Math.min(len, 1024));
                send({type: 'send', len: len, fd: args[0].toInt32()}, data);
            }
        }
    });
})();

// Hook recv
(function() {
    var libc = findModule("libc.so");
    if (!libc) return;
    var r = findExport(libc, 'recv');
    if (!r) return;
    Interceptor.attach(r.address, {
        onEnter: function(args) {
            this.buf = args[1];
            this.fd = args[0].toInt32();
        },
        onLeave: function(retval) {
            var ret = retval.toInt32();
            if (ret > 0 && ret < 65536 && this.buf) {
                var data = Memory.readByteArray(this.buf, Math.min(ret, 1024));
                send({type: 'recv', len: ret, fd: this.fd}, data);
            }
        }
    });
})();

// Hook SSL_write / SSL_read
(function() {
    var ssl = findModule("libssl.so");
    if (!ssl) return;
    var w = findExport(ssl, 'SSL_write');
    var r = findExport(ssl, 'SSL_read');
    if (w) {
        Interceptor.attach(w.address, {
            onEnter: function(args) {
                var len = args[2].toInt32();
                if (len > 0 && len < 65536) {
                    var data = Memory.readByteArray(args[1], Math.min(len, 1024));
                    send({type: 'ssl_write', len: len}, data);
                }
            }
        });
    }
    if (r) {
        Interceptor.attach(r.address, {
            onEnter: function(args) { this.buf = args[1]; },
            onLeave: function(retval) {
                var ret = retval.toInt32();
                if (ret > 0 && ret < 65536 && this.buf) {
                    var data = Memory.readByteArray(this.buf, Math.min(ret, 1024));
                    send({type: 'ssl_read', len: ret}, data);
                }
            }
        });
    }
})();

send({type: 'ready', msg: 'Monitor active. Start operating on emulator.'});
'''


def main():
    print("=" * 60)
    print("  手动操作网络监控")
    print("=" * 60)
    print(f"[INFO] 监控 PID={GAME_PID} 的 send/recv/ssl_write/ssl_read")
    print("[INFO] 请在模拟器上操作（点击战报详情、刷新等）")
    print("[INFO] 按 Ctrl+C 停止\n")

    import frida
    device = frida.get_usb_device(timeout=5)
    session = device.attach(GAME_PID)
    script = session.create_script(FRIDA_JS)

    last_activity = time.time()

    def on_message(message, data):
        if message['type'] != 'send':
            return
        payload = message['payload']
        ptype = payload.get('type')

        if ptype in ('send', 'recv', 'ssl_write', 'ssl_read') and data:
            nonlocal last_activity
            last_activity = time.time()
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]

            # 尝试多种解码方式
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

            fd_info = f" fd={payload.get('fd', 'N/A')}" if 'fd' in payload else ''
            print(f"[{ts}] [{ptype.upper():8}] {payload.get('len', 0):5} bytes{fd_info} | {preview}")

        elif ptype == 'ready':
            print(f"[OK] {payload.get('msg', '')}")

    script.on('message', on_message)
    script.load()

    try:
        while True:
            time.sleep(1)
            idle = time.time() - last_activity
            if idle > 10 and idle < 11:
                print(f"[INFO] 已 {int(idle)} 秒无网络活动...")
    except KeyboardInterrupt:
        print("\n[INFO] 停止监控")

    session.detach()


if __name__ == "__main__":
    raise SystemExit(main())
