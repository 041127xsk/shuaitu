"""
打开战报页面抓包脚本
========================
同时用两种方式抓包：
1. mitmdump 抓系统代理流量
2. Frida hook 游戏主进程的 send/recv，捕获长连接数据

用法:
    py scripts/capture_battle_open.py
    # 然后在模拟器上打开同盟战报页面
"""
import subprocess
import time
import json
import os
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
MITMDUMP = Path("C:/Users/27557/AppData/Local/Programs/Python/Python312/Scripts/mitmdump.exe")
ADB = Path("C:/Users/27557/.local/bin/platform-tools/adb.exe")
ADB_DEVICE = "127.0.0.1:16384"
PROXY_PORT = 8090

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_DIR = ROOT / "data" / "captures"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MITM_FILE = OUTPUT_DIR / f"battle_open_{TIMESTAMP}.mitm"
MITM_LOG = OUTPUT_DIR / f"battle_open_{TIMESTAMP}_mitm.txt"
FRIDA_LOG = OUTPUT_DIR / f"battle_open_{TIMESTAMP}_frida.txt"
SUMMARY_JSON = OUTPUT_DIR / f"battle_open_{TIMESTAMP}.json"

FRIDA_JS = '''
var TAG = "[BATTLE]";
var serverAddrs = {};

// 辅助：通过 /proc/self/net/tcp 读取当前连接
function readNetTcp() {
    var fopen = new NativeFunction(
        Module.findExportByName(null, "fopen"),
        'pointer', ['pointer', 'pointer']
    );
    var fgets = new NativeFunction(
        Module.findExportByName(null, "fgets"),
        'pointer', ['pointer', 'int', 'pointer']
    );
    var fclose = new NativeFunction(
        Module.findExportByName(null, "fclose"),
        'int', ['pointer']
    );
    
    var path = Memory.allocUtf8String("/proc/self/net/tcp");
    var mode = Memory.allocUtf8String("r");
    var fp = fopen(path, mode);
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

// 打印当前 TCP 连接
function printConnections() {
    var lines = readNetTcp();
    send({type: 'net_tcp', lines: lines});
}

// Hook connect
(function hookConnect() {
    var libc = Process.findModuleByName("libc.so");
    if (!libc) {
        var mods = Process.enumerateModules();
        libc = mods.find(function(m) { return m.name.indexOf('libc.so') !== -1; });
    }
    if (!libc) {
        send({type: 'error', msg: 'libc.so not found'});
        return;
    }
    
    var exports = libc.enumerateExports();
    var conn = exports.find(function(e) { return e.name === 'connect'; });
    if (!conn) {
        send({type: 'error', msg: 'connect not found in libc'});
        return;
    }
    
    Interceptor.attach(conn.address, {
        onEnter: function(args) {
            var sockaddr = args[1];
            var family = Memory.readU16(sockaddr);
            if (family === 2) { // AF_INET
                var port = Memory.readU16(sockaddr.add(2));
                port = ((port & 0xFF) << 8) | ((port >> 8) & 0xFF);
                var ip = [];
                for (var i = 0; i < 4; i++) {
                    ip.push(Memory.readU8(sockaddr.add(4 + i)));
                }
                var addr = ip.join('.') + ':' + port;
                serverAddrs[addr] = true;
                send({type: 'connect', addr: addr});
            }
        }
    });
    send({type: 'info', msg: 'connect() hooked'});
})();

// Hook send
(function hookSend() {
    var libc = Process.findModuleByName("libc.so");
    if (!libc) {
        var mods = Process.enumerateModules();
        libc = mods.find(function(m) { return m.name.indexOf('libc.so') !== -1; });
    }
    if (!libc) return;
    
    var exports = libc.enumerateExports();
    var s = exports.find(function(e) { return e.name === 'send'; });
    if (!s) {
        send({type: 'error', msg: 'send not found'});
        return;
    }
    
    Interceptor.attach(s.address, {
        onEnter: function(args) {
            var len = args[2].toInt32();
            if (len > 0 && len < 8192) {
                var data = Memory.readByteArray(args[1], len);
                send({type: 'send', len: len}, data);
            }
        }
    });
    send({type: 'info', msg: 'send() hooked'});
})();

// Hook recv
(function hookRecv() {
    var libc = Process.findModuleByName("libc.so");
    if (!libc) {
        var mods = Process.enumerateModules();
        libc = mods.find(function(m) { return m.name.indexOf('libc.so') !== -1; });
    }
    if (!libc) return;
    
    var exports = libc.enumerateExports();
    var r = exports.find(function(e) { return e.name === 'recv'; });
    if (!r) return;
    
    Interceptor.attach(r.address, {
        onLeave: function(retval) {
            var len = retval.toInt32();
            if (len > 0 && len < 8192) {
                // recv 的 buf 在 onEnter 时保存
            }
        }
    });
    send({type: 'info', msg: 'recv() hooked (basic)'});
})();

// 每 5 秒打印一次当前连接
setInterval(printConnections, 5000);
printConnections();

send({type: 'ready', msg: 'All hooks applied. Open battle page now.'});
'''


def set_proxy():
    print("[1] 设置模拟器代理...")
    subprocess.run(
        [str(ADB), "-s", ADB_DEVICE, "shell", "settings", "put", "global", "http_proxy", f"10.0.2.2:{PROXY_PORT}"],
        capture_output=True,
    )


def clear_proxy():
    print("[5] 清除模拟器代理...")
    subprocess.run([str(ADB), "-s", ADB_DEVICE, "shell", "settings", "put", "global", "http_proxy", ":0"], capture_output=True)
    subprocess.run([str(ADB), "-s", ADB_DEVICE, "shell", "settings", "delete", "global", "http_proxy"], capture_output=True)


def start_mitmdump():
    print(f"[2] 启动 mitmdump...")
    proc = subprocess.Popen(
        [str(MITMDUMP), "-p", str(PROXY_PORT), "--ssl-insecure", "-w", str(MITM_FILE)],
        stdout=open(str(MITM_LOG), "w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
    )
    time.sleep(2)
    print(f"[OK] mitmdump PID={proc.pid}")
    return proc


def start_frida_monitor():
    print("[3] 启动 Frida 网络监控...")
    import frida

    device = frida.get_usb_device(timeout=3)
    session = device.attach(3207)

    script = session.create_script(FRIDA_JS)
    frida_records = []

    def on_message(message, data):
        if message['type'] == 'send':
            payload = message['payload']
            frida_records.append(payload)
            ptype = payload.get('type')
            if ptype == 'connect':
                print(f"    [Frida] CONNECT -> {payload['addr']}")
            elif ptype == 'send':
                # 尝试解码前 200 字节
                if data:
                    try:
                        text = data.decode('utf-8', errors='ignore')[:200]
                        if text.strip():
                            print(f"    [Frida] SEND ({payload.get('len')} bytes): {text[:80]}")
                    except:
                        pass
            elif ptype == 'net_tcp':
                print(f"    [Frida] Current TCP connections:")
                for line in payload.get('lines', [])[:8]:
                    print(f"        {line}")
            elif ptype == 'ready':
                print(f"    [Frida] {payload.get('msg')}")

    script.on('message', on_message)
    script.load()
    print("[OK] Frida 监控已启动")
    return session, script, frida_records


def main():
    print("=" * 60)
    print("  战报页面打开抓包工具")
    print("=" * 60)

    if not MITMDUMP.exists():
        print(f"[!] 找不到 mitmdump")
        return 1

    # 设置代理
    set_proxy()

    # 启动抓包
    mitm_proc = start_mitmdump()

    # 启动 Frida 监控
    try:
        session, script, frida_records = start_frida_monitor()
    except Exception as e:
        print(f"[!] Frida 启动失败: {e}")
        session = None
        frida_records = []

    # 给用户操作时间
    print("\n[4] 请在 10 秒内打开同盟战报页面...")
    print("    (脚本会自动记录这段时间内的所有网络活动)")
    time.sleep(10)

    # 停止
    print("\n[5] 停止抓包...")
    mitm_proc.terminate()
    try:
        mitm_proc.wait(timeout=5)
    except:
        mitm_proc.kill()

    if session:
        session.detach()

    clear_proxy()

    # 分析 mitmdump 结果
    mitm_urls = []
    if MITM_LOG.exists():
        with open(MITM_LOG, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if "://" in line and ("GET " in line or "POST " in line):
                    mitm_urls.append(line)

    # 保存摘要
    summary = {
        "timestamp": datetime.now().isoformat(),
        "mitm_file": str(MITM_FILE),
        "mitm_log": str(MITM_LOG),
        "frida_log": str(FRIDA_LOG),
        "mitm_urls": mitm_urls,
        "frida_events": frida_records,
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    print(f"\n[OK] 完成!")
    print(f"    mitmdump 流量: {MITM_FILE}")
    print(f"    Frida 事件数: {len(frida_records)}")
    print(f"    系统代理 URL: {len(mitm_urls)} 条")
    print(f"    摘要: {SUMMARY_JSON}")

    # 打印关键发现
    connects = [e for e in frida_records if e.get('type') == 'connect']
    if connects:
        print(f"\n[发现] Frida 捕获到 {len(connects)} 个新连接:")
        for c in connects:
            print(f"    -> {c['addr']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
