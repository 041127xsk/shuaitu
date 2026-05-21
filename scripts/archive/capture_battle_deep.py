"""
深度网络监控脚本
================
Hook 所有可能的网络/IO 接口，找出战报数据到底走哪条路。

用法:
    py scripts/capture_battle_deep.py
"""
import subprocess
import time
import json
import threading
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
ADB = Path("C:/Users/27557/.local/bin/platform-tools/adb.exe")
ADB_DEVICE = "127.0.0.1:16384"
GAME_PID = 3207

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_DIR = ROOT / "data" / "captures"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FRIDA_LOG = OUTPUT_DIR / f"battle_deep_{TIMESTAMP}.txt"
SUMMARY_JSON = OUTPUT_DIR / f"battle_deep_{TIMESTAMP}.json"

SWIPE_X = 960
SWIPE_Y_START = 850
SWIPE_Y_END = 450
SWIPE_DURATION = 400

FRIDA_JS = '''
var TAG = "[DEEP]";

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

function hookFunc(modName, funcName, handler) {
    var mod = findModule(modName);
    if (!mod) { send({type: 'warn', msg: modName + ' not found'}); return; }
    var exp = findExport(mod, funcName);
    if (!exp) { send({type: 'warn', msg: funcName + ' not found in ' + modName}); return; }
    
    Interceptor.attach(exp.address, handler);
    send({type: 'info', msg: funcName + '() hooked in ' + modName});
}

// 1. libc socket
hookFunc("libc.so", "connect", {
    onEnter: function(args) {
        var sockaddr = args[1];
        var family = Memory.readU16(sockaddr);
        if (family === 2) {
            var port = Memory.readU16(sockaddr.add(2));
            port = ((port & 0xFF) << 8) | ((port >> 8) & 0xFF);
            var ip = [];
            for (var i = 0; i < 4; i++) ip.push(Memory.readU8(sockaddr.add(4 + i)));
            send({type: 'connect', addr: ip.join('.') + ':' + port});
        }
    }
});

hookFunc("libc.so", "send", {
    onEnter: function(args) {
        var len = args[2].toInt32();
        if (len > 0 && len < 32768) {
            var data = Memory.readByteArray(args[1], Math.min(len, 512));
            send({type: 'send', len: len}, data);
        }
    }
});

hookFunc("libc.so", "sendto", {
    onEnter: function(args) {
        var len = args[2].toInt32();
        if (len > 0 && len < 32768) {
            var data = Memory.readByteArray(args[1], Math.min(len, 512));
            send({type: 'sendto', len: len}, data);
        }
    }
});

hookFunc("libc.so", "recv", {
    onEnter: function(args) { this.buf = args[1]; },
    onLeave: function(retval) {
        var ret = retval.toInt32();
        if (ret > 0 && ret < 32768 && this.buf) {
            var data = Memory.readByteArray(this.buf, Math.min(ret, 512));
            send({type: 'recv', len: ret}, data);
        }
    }
});

hookFunc("libc.so", "recvfrom", {
    onEnter: function(args) { this.buf = args[1]; },
    onLeave: function(retval) {
        var ret = retval.toInt32();
        if (ret > 0 && ret < 32768 && this.buf) {
            var data = Memory.readByteArray(this.buf, Math.min(ret, 512));
            send({type: 'recvfrom', len: ret}, data);
        }
    }
});

// 2. libc read/write (可能用于 pipe/socket fd)
hookFunc("libc.so", "write", {
    onEnter: function(args) {
        var len = args[2].toInt32();
        if (len > 0 && len < 32768) {
            var data = Memory.readByteArray(args[1], Math.min(len, 512));
            send({type: 'write', len: len}, data);
        }
    }
});

hookFunc("libc.so", "read", {
    onEnter: function(args) { this.buf = args[1]; this.fd = args[0].toInt32(); },
    onLeave: function(retval) {
        var ret = retval.toInt32();
        if (ret > 0 && ret < 32768 && this.buf) {
            var data = Memory.readByteArray(this.buf, Math.min(ret, 512));
            send({type: 'read', len: ret, fd: this.fd}, data);
        }
    }
});

// 3. libssl
hookFunc("libssl.so", "SSL_write", {
    onEnter: function(args) {
        var len = args[2].toInt32();
        if (len > 0 && len < 32768) {
            var data = Memory.readByteArray(args[1], Math.min(len, 512));
            send({type: 'ssl_write', len: len}, data);
        }
    }
});

hookFunc("libssl.so", "SSL_read", {
    onEnter: function(args) { this.buf = args[1]; },
    onLeave: function(retval) {
        var ret = retval.toInt32();
        if (ret > 0 && ret < 32768 && this.buf) {
            var data = Memory.readByteArray(this.buf, Math.min(ret, 512));
            send({type: 'ssl_read', len: ret}, data);
        }
    }
});

// 4. libcrypto (可能有用)
hookFunc("libcrypto.so", "BIO_write", {
    onEnter: function(args) {
        var len = args[2].toInt32();
        if (len > 0 && len < 32768) {
            var data = Memory.readByteArray(args[1], Math.min(len, 512));
            send({type: 'bio_write', len: len}, data);
        }
    }
});

// 5. 同时监控 /proc/self/net/tcp 里的连接变化
function readNetTcp() {
    var fopen = new NativeFunction(findExport(findModule("libc.so"), "fopen"), 'pointer', ['pointer', 'pointer']);
    var fgets = new NativeFunction(findExport(findModule("libc.so"), "fgets"), 'pointer', ['pointer', 'int', 'pointer']);
    var fclose = new NativeFunction(findExport(findModule("libc.so"), "fclose"), 'int', ['pointer']);
    
    var fp = fopen(Memory.allocUtf8String("/proc/self/net/tcp"), Memory.allocUtf8String("r"));
    if (fp.isNull()) return [];
    var buf = Memory.alloc(512);
    var lines = [];
    while (true) {
        var ret = fgets(buf, 512, fp);
        if (ret.isNull()) break;
        lines.push(Memory.readUtf8String(buf).trim());
    }
    fclose(fp);
    return lines;
}

setInterval(function() {
    var lines = readNetTcp();
    // 只发送有 ESTABLISHED 状态的行
    var active = lines.filter(function(l) { return l.indexOf('01 ') !== -1; });
    if (active.length > 0) {
        send({type: 'net_tcp', count: active.length, lines: active.slice(0, 5)});
    }
}, 3000);

send({type: 'ready', msg: 'Deep hooks applied'});
'''


def adb_cmd(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(ADB), "-s", ADB_DEVICE] + cmd,
        capture_output=True, text=True,
    )


def swipe_up():
    adb_cmd([
        "shell", "input", "swipe",
        str(SWIPE_X), str(SWIPE_Y_START),
        str(SWIPE_X), str(SWIPE_Y_END),
        str(SWIPE_DURATION),
    ])


def tap(x: int, y: int):
    adb_cmd(["shell", "input", "tap", str(x), str(y)])


def auto_scroll(count: int, interval: float, stop_event: threading.Event):
    for i in range(count):
        if stop_event.is_set():
            break
        swipe_up()
        time.sleep(interval)
        if i % 4 == 3:
            tap(SWIPE_X, 1200)
            time.sleep(0.3)
    print("    [翻页] 完成")


def main():
    print("=" * 60)
    print("  深度网络监控 + 翻页")
    print("=" * 60)

    import frida

    r = adb_cmd(["shell", "echo", "ok"])
    if r.returncode != 0:
        print(f"[!] adb 失败: {r.stderr}")
        return 1
    print("[OK] adb 已连接")

    print(f"[1] 启动 Frida deep hooks，PID={GAME_PID}...")
    device = frida.get_usb_device(timeout=5)
    session = device.attach(GAME_PID)
    script = session.create_script(FRIDA_JS)

    text_fh = open(str(FRIDA_LOG), "w", encoding="utf-8")
    stats = {
        'connect': [], 'send': 0, 'sendto': 0, 'recv': 0, 'recvfrom': 0,
        'write': 0, 'read': 0, 'ssl_write': 0, 'ssl_read': 0, 'bio_write': 0,
        'net_tcp': []
    }
    first_data = None

    def on_message(message, data):
        if message['type'] != 'send':
            return
        payload = message['payload']
        ptype = payload.get('type')

        if ptype == 'connect':
            addr = payload['addr']
            if addr not in stats['connect']:
                stats['connect'].append(addr)
                line = f"[CONNECT] {addr}"
                print(f"    {line}")
                text_fh.write(line + "\n")
                text_fh.flush()

        elif ptype in ('send', 'sendto', 'recv', 'recvfrom', 'write', 'read', 'ssl_write', 'ssl_read', 'bio_write'):
            stats[ptype] = stats.get(ptype, 0) + 1
            if data:
                try:
                    preview = data.decode('utf-8', errors='ignore')[:80].replace('\n', ' ')
                    if preview.strip():
                        line = f"[{ptype.upper()} {payload.get('len', 0)}b] {preview}"
                        print(f"    {line}")
                        text_fh.write(line + "\n")
                        text_fh.flush()
                        nonlocal first_data
                        if first_data is None:
                            first_data = (ptype, preview)
                except:
                    pass

        elif ptype == 'net_tcp':
            for line in payload.get('lines', []):
                if line not in stats['net_tcp']:
                    stats['net_tcp'].append(line)
                    print(f"    [TCP] {line}")
                    text_fh.write(f"[TCP] {line}\n")
                    text_fh.flush()

        elif ptype in ('info', 'warn', 'error'):
            line = f"[{ptype.upper()}] {payload.get('msg', '')}"
            print(f"    {line}")
            text_fh.write(line + "\n")
            text_fh.flush()

    script.on('message', on_message)
    script.load()
    print("[OK] Deep hooks 已注入")

    time.sleep(1)

    print(f"\n[2] 自动翻页 (15 次)...")
    stop_event = threading.Event()
    scroll_thread = threading.Thread(target=auto_scroll, args=(15, 1.5, stop_event))
    scroll_thread.start()

    try:
        scroll_thread.join()
    except KeyboardInterrupt:
        stop_event.set()
        scroll_thread.join(timeout=5)

    print("\n[3] 停止...")
    session.detach()
    text_fh.close()

    summary = {
        "timestamp": datetime.now().isoformat(),
        "game_pid": GAME_PID,
        "connections": stats['connect'],
        "stats": {k: v for k, v in stats.items() if k != 'net_tcp'},
        "tcp_lines": stats['net_tcp'],
        "first_data": first_data,
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    print(f"\n[OK] 完成!")
    print(f"    日志: {FRIDA_LOG}")
    print(f"    摘要: {SUMMARY_JSON}")
    print(f"\n[统计]")
    for k, v in summary['stats'].items():
        if isinstance(v, list):
            print(f"    {k}: {len(v)} 条")
        else:
            print(f"    {k}: {v} 次")
    if summary['connections']:
        print(f"\n[连接] {', '.join(summary['connections'])}")
    if first_data:
        print(f"\n[首条数据] {first_data[0]}: {first_data[1]}")
    else:
        print(f"\n[!] 警告: 未捕获到任何网络/IO 数据")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
