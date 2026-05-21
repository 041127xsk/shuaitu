"""
战报翻页长连接抓包脚本
========================
用 Frida hook 游戏主进程的 send/recv/connect，同时 adb 自动翻页触发新请求。
游戏使用长连接，不走系统代理，所以不用 mitmproxy。

用法:
    py scripts/capture_battle_scroll.py
    # 确保模拟器已在战报页面，脚本会自动翻页并抓包
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
GAME_PID = 3207  # com.netease.stzb.uc 主进程

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_DIR = ROOT / "data" / "captures"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FRIDA_LOG = OUTPUT_DIR / f"battle_scroll_{TIMESTAMP}_frida.txt"
SEND_LOG = OUTPUT_DIR / f"battle_scroll_{TIMESTAMP}_send.bin"
RECV_LOG = OUTPUT_DIR / f"battle_scroll_{TIMESTAMP}_recv.bin"
SUMMARY_JSON = OUTPUT_DIR / f"battle_scroll_{TIMESTAMP}.json"

# 屏幕参数：横屏 1920x1080
SWIPE_X = 960
SWIPE_Y_START = 850
SWIPE_Y_END = 450
SWIPE_DURATION = 400

FRIDA_JS = '''
var TAG = "[BATTLE]";
var sendLog = [];
var recvLog = [];
var connections = [];

function findModule(name) {
    var m = Process.findModuleByName(name);
    if (m) return m;
    var mods = Process.enumerateModules();
    return mods.find(function(mod) { return mod.name.indexOf(name) !== -1; });
}

function findExport(mod, name) {
    var exports = mod.enumerateExports();
    return exports.find(function(e) { return e.name === name; });
}

// Hook connect
(function() {
    var libc = findModule("libc.so");
    if (!libc) { send({type: 'error', msg: 'libc.so not found'}); return; }
    var conn = findExport(libc, 'connect');
    if (!conn) { send({type: 'error', msg: 'connect not found'}); return; }
    
    Interceptor.attach(conn.address, {
        onEnter: function(args) {
            var sockaddr = args[1];
            var family = Memory.readU16(sockaddr);
            if (family === 2) {
                var port = Memory.readU16(sockaddr.add(2));
                port = ((port & 0xFF) << 8) | ((port >> 8) & 0xFF);
                var ip = [];
                for (var i = 0; i < 4; i++) ip.push(Memory.readU8(sockaddr.add(4 + i)));
                var addr = ip.join('.') + ':' + port;
                connections.push(addr);
                send({type: 'connect', addr: addr});
            }
        }
    });
    send({type: 'info', msg: 'connect() hooked'});
})();

// Hook send
(function() {
    var libc = findModule("libc.so");
    if (!libc) return;
    var s = findExport(libc, 'send');
    if (!s) { send({type: 'error', msg: 'send not found'}); return; }
    
    Interceptor.attach(s.address, {
        onEnter: function(args) {
            var len = args[2].toInt32();
            if (len > 0 && len < 32768) {
                var data = Memory.readByteArray(args[1], len);
                send({type: 'send', len: len}, data);
            }
        }
    });
    send({type: 'info', msg: 'send() hooked'});
})();

// Hook recv - 需要保存 buf 指针
(function() {
    var libc = findModule("libc.so");
    if (!libc) return;
    var r = findExport(libc, 'recv');
    if (!r) { send({type: 'error', msg: 'recv not found'}); return; }
    
    Interceptor.attach(r.address, {
        onEnter: function(args) {
            this.buf = args[1];
            this.len = args[2].toInt32();
        },
        onLeave: function(retval) {
            var ret = retval.toInt32();
            if (ret > 0 && ret < 32768 && this.buf) {
                var data = Memory.readByteArray(this.buf, ret);
                send({type: 'recv', len: ret}, data);
            }
        }
    });
    send({type: 'info', msg: 'recv() hooked'});
})();

send({type: 'ready', msg: 'All hooks applied. Starting scroll capture...'});
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
    """后台线程：持续翻页直到收到停止信号"""
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
    print("  战报翻页长连接抓包工具")
    print("=" * 60)

    import frida

    # 检查设备
    r = adb_cmd(["shell", "echo", "ok"])
    if r.returncode != 0:
        print(f"[!] adb 连接失败: {r.stderr}")
        return 1
    print("[OK] adb 已连接")

    # 启动 Frida
    print(f"[1] 启动 Frida，attach PID={GAME_PID}...")
    device = frida.get_usb_device(timeout=5)
    session = device.attach(GAME_PID)
    script = session.create_script(FRIDA_JS)

    send_fh = open(str(SEND_LOG), "wb")
    recv_fh = open(str(RECV_LOG), "wb")
    text_fh = open(str(FRIDA_LOG), "w", encoding="utf-8")
    frida_records = []

    def on_message(message, data):
        if message['type'] != 'send':
            return
        payload = message['payload']
        frida_records.append(payload)
        ptype = payload.get('type')

        if ptype == 'connect':
            line = f"[CONNECT] {payload['addr']}"
            print(f"    {line}")
            text_fh.write(line + "\n")
            text_fh.flush()

        elif ptype == 'send' and data:
            send_fh.write(data)
            send_fh.flush()
            # 尝试打印前 100 字节
            try:
                preview = data.decode('utf-8', errors='ignore')[:100].replace('\n', ' ')
                if preview.strip():
                    line = f"[SEND {payload.get('len')} bytes] {preview}"
                    print(f"    {line}")
                    text_fh.write(line + "\n")
                    text_fh.flush()
            except:
                pass

        elif ptype == 'recv' and data:
            recv_fh.write(data)
            recv_fh.flush()
            try:
                preview = data.decode('utf-8', errors='ignore')[:100].replace('\n', ' ')
                if preview.strip():
                    line = f"[RECV {payload.get('len')} bytes] {preview}"
                    print(f"    {line}")
                    text_fh.write(line + "\n")
                    text_fh.flush()
            except:
                pass

        elif ptype == 'info':
            line = f"[INFO] {payload.get('msg', '')}"
            print(f"    {line}")
            text_fh.write(line + "\n")
            text_fh.flush()

        elif ptype == 'error':
            line = f"[ERROR] {payload.get('msg', '')}"
            print(f"    {line}")
            text_fh.write(line + "\n")
            text_fh.flush()

    script.on('message', on_message)
    script.load()
    print("[OK] Frida hooks 已注入")

    # 等待一下让 hook 稳定
    time.sleep(1)

    # 启动翻页线程
    print(f"\n[2] 开始自动翻页 (20 次，间隔 1.5 秒)...")
    print("    请确保模拟器当前在战报列表页面\n")
    stop_event = threading.Event()
    scroll_thread = threading.Thread(target=auto_scroll, args=(20, 1.5, stop_event))
    scroll_thread.start()

    try:
        scroll_thread.join()
    except KeyboardInterrupt:
        print("\n[!] 用户中断")
        stop_event.set()
        scroll_thread.join(timeout=5)

    # 收尾
    print("\n[3] 停止抓包...")
    session.detach()
    send_fh.close()
    recv_fh.close()
    text_fh.close()

    # 分析
    connects = [e for e in frida_records if e.get('type') == 'connect']
    sends = [e for e in frida_records if e.get('type') == 'send']
    recvs = [e for e in frida_records if e.get('type') == 'recv']

    summary = {
        "timestamp": datetime.now().isoformat(),
        "game_pid": GAME_PID,
        "frida_log": str(FRIDA_LOG),
        "send_log": str(SEND_LOG),
        "recv_log": str(RECV_LOG),
        "connections": list(set(connects)),
        "send_count": len(sends),
        "recv_count": len(recvs),
        "send_bytes": SEND_LOG.stat().st_size if SEND_LOG.exists() else 0,
        "recv_bytes": RECV_LOG.stat().st_size if RECV_LOG.exists() else 0,
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    print(f"\n[OK] 完成!")
    print(f"    文本日志: {FRIDA_LOG}")
    print(f"    发送数据: {SEND_LOG} ({summary['send_bytes']} bytes)")
    print(f"    接收数据: {RECV_LOG} ({summary['recv_bytes']} bytes)")
    print(f"    连接数: {len(summary['connections'])}")
    print(f"    发送包: {summary['send_count']}, 接收包: {summary['recv_count']}")
    print(f"    摘要: {SUMMARY_JSON}")

    if summary['connections']:
        print(f"\n[发现] 连接目标:")
        for c in summary['connections']:
            print(f"    -> {c}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
