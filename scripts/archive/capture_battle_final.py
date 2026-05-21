"""
战报页面进入抓包（最终版）
==========================
专门捕获进入"同盟战报"页面时的 sendto/recvfrom 完整数据。

用法:
    1. 确保模拟器在主界面（不在战报页面）
    2. py scripts/capture_battle_final.py
    3. 脚本提示后，点击"同盟战报"进入页面
    4. 等待 10 秒自动停止
"""
import frida
import time
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
GAME_PID = 4568

TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_DIR = ROOT / "data" / "captures"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DATA_LOG = OUTPUT_DIR / f"battle_final_{TIMESTAMP}.txt"
HEX_LOG = OUTPUT_DIR / f"battle_final_{TIMESTAMP}.hex"

FRIDA_JS = '''
function findExport(mod, name) {
    if (!mod) return null;
    var exports = mod.enumerateExports();
    return exports.find(function(e) { return e.name === name; });
}

var libc = Process.findModuleByName("libc.so");

// sendto
var sendtoAddr = findExport(libc, "sendto");
if (sendtoAddr) {
    Interceptor.attach(sendtoAddr.address, {
        onEnter: function(args) {
            var len = args[2].toInt32();
            if (len > 0 && len < 65536) {
                var data = Memory.readByteArray(args[1], len);
                send({type: 'sendto', len: len}, data);
            }
        }
    });
}

// recvfrom
var recvfromAddr = findExport(libc, "recvfrom");
if (recvfromAddr) {
    Interceptor.attach(recvfromAddr.address, {
        onEnter: function(args) {
            this.buf = args[1];
            this.len = args[2].toInt32();
        },
        onLeave: function(retval) {
            var ret = retval.toInt32();
            if (ret > 0 && ret < 65536 && this.buf) {
                var data = Memory.readByteArray(this.buf, ret);
                send({type: 'recvfrom', len: ret}, data);
            }
        }
    });
}

send({type: 'ready', msg: 'Hooks active'});
'''


def main():
    print("=" * 60)
    print("  战报页面进入抓包（最终版）")
    print("=" * 60)
    print("[步骤]")
    print("  1. 确保模拟器当前不在战报页面（返回主界面）")
    print("  2. 脚本启动后，点击'同盟战报'进入页面")
    print("  3. 等待 10 秒自动完成\n")

    print("[INFO] 3 秒后自动开始...")
    time.sleep(3)

    device = frida.get_usb_device(timeout=5)
    session = device.attach(GAME_PID)
    script = session.create_script(FRIDA_JS)

    data_fh = open(str(DATA_LOG), "w", encoding="utf-8")
    hex_fh = open(str(HEX_LOG), "w", encoding="utf-8")

    sendto_count = 0
    recvfrom_count = 0

    def on_message(msg, data):
        nonlocal sendto_count, recvfrom_count
        if msg['type'] != 'send':
            return
        p = msg['payload']
        t = p.get('type')

        if t == 'sendto' and data:
            sendto_count += 1
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            
            # 尝试解码
            text = ""
            for enc in ['utf-8', 'gbk', 'latin-1']:
                try:
                    text = data.decode(enc, errors='ignore')[:300].replace('\n', ' ').replace('\r', '')
                    if text.strip():
                        break
                except:
                    pass
            
            print(f"\n[{ts}] === SENDTO #{sendto_count} ({p['len']} bytes) ===")
            print(f"  TEXT: {text[:150]}")
            
            data_fh.write(f"\n=== SENDTO #{sendto_count} {p['len']} bytes ===\n")
            data_fh.write(text + "\n")
            data_fh.flush()
            
            hex_fh.write(f"\n=== SENDTO #{sendto_count} {p['len']} bytes ===\n")
            hex_fh.write(data.hex())
            hex_fh.write("\n")
            hex_fh.flush()

        elif t == 'recvfrom' and data:
            recvfrom_count += 1
            ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            
            text = ""
            for enc in ['utf-8', 'gbk', 'latin-1']:
                try:
                    text = data.decode(enc, errors='ignore')[:300].replace('\n', ' ').replace('\r', '')
                    if text.strip():
                        break
                except:
                    pass
            
            print(f"\n[{ts}] === RECVFROM #{recvfrom_count} ({p['len']} bytes) ===")
            print(f"  TEXT: {text[:150]}")
            
            data_fh.write(f"\n=== RECVFROM #{recvfrom_count} {p['len']} bytes ===\n")
            data_fh.write(text + "\n")
            data_fh.flush()
            
            hex_fh.write(f"\n=== RECVFROM #{recvfrom_count} {p['len']} bytes ===\n")
            hex_fh.write(data.hex())
            hex_fh.write("\n")
            hex_fh.flush()

        elif t == 'ready':
            print(f"[OK] {p['msg']}")

    script.on('message', on_message)
    script.load()

    print("\n[OK] Hooks 已注入！")
    print("[ACTION] 现在请在模拟器上点击'同盟战报'进入页面！")
    print("[WAIT] 监控 12 秒...\n")

    time.sleep(12)

    session.detach()
    data_fh.close()
    hex_fh.close()

    print(f"\n[OK] 完成!")
    print(f"    SENDTO: {sendto_count} 次")
    print(f"    RECVFROM: {recvfrom_count} 次")
    print(f"    文本日志: {DATA_LOG}")
    print(f"    HEX 日志: {HEX_LOG}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
