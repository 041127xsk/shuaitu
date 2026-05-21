"""
率土之滨 SSL Unpinning + 战报接口捕获
Frida Script: Hook 游戏进程，绕过 SSL Pinning
配合 mitmdump (端口 8090) 使用
"""
import frida, sys, json, time
from datetime import datetime

GAME_PROCESS = None  # 自动发现

def on_message(message, data):
    """接收 Frida 脚本发来的消息"""
    if message['type'] == 'send':
        payload = message['payload']
        print(f"[Frida] {payload}")
    elif message['type'] == 'error':
        print(f"[Frida Error] {message['stack']}")

def get_stzb_process():
    """查找率土之滨进程名"""
    import subprocess
    adb = r'C:\Users\27557\.local\bin\platform-tools\adb.exe'
    # 列出所有进程，找游戏
    r = subprocess.run([
        adb, '-s', '127.0.0.1:16384', 'shell',
        'ps -A | grep -iE "stz|stzb|sango|netease|game|unity"'
    ], capture_output=True, text=True, timeout=10)
    lines = [l for l in r.stdout.strip().split('\n') if l]
    # 先打印所有进程
    candidates = []
    for line in lines:
        parts = line.split()
        if len(parts) >= 9:
            pid = parts[1]
            name = parts[-1]
            # 状态通常在第8列 (索引7或8)
            state = ''
            for i, p in enumerate(parts):
                if p in ['R', 'S', 'D', 'Z', 'T', 't', 'X', 'x', 'K', 'W']:
                    state = p
                    break
            print(f"  进程 {pid}: {name} [{state}]")
            if state == 'Z':
                continue
            if 'stzb' in name.lower() or 'stz' in name.lower():
                candidates.append((pid, name))
    
    # 优先返回 com.netease.stzb.uc 主进程（不含 :PushService）
    for pid, name in candidates:
        if name == 'com.netease.stzb.uc':
            return pid, name
    # 其次返回其他 stzb 进程
    if candidates:
        return candidates[0]
    
    # 最后返回第一个非僵尸进程
    for line in lines[:10]:
        parts = line.split()
        if len(parts) >= 9:
            state = parts[4] if len(parts) > 4 else ''
            if state != 'Z':
                return parts[1], parts[-1]
    return None, None

# ============================================================
# Frida 脚本：绕过 SSL Pinning
# ============================================================
FRIDA_SCRIPT = """
(function () {
    var TAG = "[SSL-Unpin]";
    var hookCount = 0;

    function log(msg) {
        send(TAG + " " + msg);
    }

    function tryHook(name, fn) {
        try {
            fn();
            hookCount++;
            log("[OK] " + name);
        } catch (e) {
            log("[SKIP] " + name + ": " + e.message);
        }
    }

    // 辅助：通过 enumerateExports 查找符号地址（兼容 findExportByName 不可用的进程）
    function findExportAddr(moduleName, exportName) {
        var mods = Process.enumerateModules();
        var mod = mods.find(function(m) { return m.name === moduleName; });
        if (!mod) throw new Error("module not found: " + moduleName);
        var exports = mod.enumerateExports();
        var found = exports.find(function(e) { return e.name === exportName; });
        if (!found) throw new Error("export not found: " + exportName);
        return found.address;
    }

    // ============================================================
    // Native 层 Hook (Unity 游戏常用)
    // ============================================================

    // ---- Hook 1: SSL_CTX_set_custom_verify (BoringSSL / Android) ----
    tryHook("SSL_CTX_set_custom_verify", function () {
        var addr = findExportAddr("libssl.so", "SSL_CTX_set_custom_verify");
        Interceptor.attach(addr, {
            onEnter: function (args) {
                // args[2] 是回调函数指针，替换成返回 0 的空函数
                var callbackPtr = args[2];
                if (callbackPtr.isNull()) return;
                var nop = new NativeCallback(function () { return 0; }, 'int', []);
                args[2] = nop;
                log("SSL_CTX_set_custom_verify callback replaced");
            }
        });
    });

    // ---- Hook 2: SSL_set_verify (OpenSSL) ----
    tryHook("SSL_set_verify", function () {
        var addr = findExportAddr("libssl.so", "SSL_set_verify");
        Interceptor.attach(addr, {
            onEnter: function (args) {
                args[1] = ptr(0x00); // SSL_VERIFY_NONE
                log("SSL_set_verify -> SSL_VERIFY_NONE");
            }
        });
    });

    // ---- Hook 3: X509_verify_cert (证书链验证) ----
    tryHook("X509_verify_cert", function () {
        var addr = findExportAddr("libssl.so", "X509_verify_cert");
        Interceptor.replace(addr, new NativeCallback(function () {
            return 1; // 永远返回验证成功
        }, 'int', ['pointer']));
    });

    // ---- Hook 4: SSL_CTX_set_verify (设置全局验证模式) ----
    tryHook("SSL_CTX_set_verify", function () {
        var addr = findExportAddr("libssl.so", "SSL_CTX_set_verify");
        Interceptor.attach(addr, {
            onEnter: function (args) {
                args[1] = ptr(0x00);
                log("SSL_CTX_set_verify -> SSL_VERIFY_NONE");
            }
        });
    });

    // ---- Hook 5: SSL_set_custom_verify (BoringSSL) ----
    tryHook("SSL_set_custom_verify", function () {
        var addr = findExportAddr("libssl.so", "SSL_set_custom_verify");
        Interceptor.attach(addr, {
            onEnter: function (args) {
                var callbackPtr = args[2];
                if (callbackPtr.isNull()) return;
                var nop = new NativeCallback(function () { return 0; }, 'int', []);
                args[2] = nop;
                log("SSL_set_custom_verify callback replaced");
            }
        });
    });

    // ============================================================
    // Java 层 Hook (Fallback)
    // ============================================================
    if (typeof Java !== 'undefined') {
        Java.perform(function () {
            tryHook("OkHttp3", function () {
                var OkHostnameVerifier = Java.use('okhttp3.internal.tls.OkHostnameVerifier');
                OkHostnameVerifier.verify.overload('java.lang.String', 'javax.net.ssl.SSLSession').implementation = function () { return true; };
            });
            tryHook("TrustManagerImpl", function () {
                var tmi = Java.use('com.android.org.conscrypt.TrustManagerImpl');
                tmi.checkServerTrusted.overload('[Ljava.security.cert.X509Certificate;', 'java.lang.String', 'java.lang.String').implementation = function () {};
            });
            tryHook("WebViewClient", function () {
                var WVC = Java.use('android.webkit.WebViewClient');
                WVC.onReceivedSslError.overload('android.webkit.WebView', 'android.webkit.SslErrorHandler', 'android.net.http.SslError').implementation = function (view, handler) {
                    handler.proceed();
                };
            });
        });
    } else {
        log("[INFO] Java runtime not available, skipping Java hooks");
    }

    log("Completed. Active hooks: " + hookCount);
})();
"""

def main():
    global GAME_PROCESS

    print("=" * 60)
    print("  率土 SSL Unpinning 工具")
    print("=" * 60)

    # 查找游戏进程
    print("\n[1] 查找率土进程...")
    pid, name = get_stzb_process()
    if not pid:
        print("[!] 未找到游戏进程，请确保游戏已启动！")
        print("[!] 请手动指定进程名，方法：")
        print("    adb shell 'ps -A' | grep stz")
        return

    GAME_PROCESS = pid
    print(f"[OK] 找到游戏进程: PID={pid}, Name={name}")

    # 连接 frida-server
    print(f"\n[2] 连接 frida-server...")
    try:
        # 先尝试 USB
        device = frida.get_usb_device(timeout=3)
        print(f"[OK] USB 设备: {device.id} ({device.name})")
    except Exception as e:
        print(f"[!] USB 连接失败: {e}")
        print("[!] 尝试远程连接...")
        try:
            import subprocess
            subprocess.run([
                r'C:\Users\27557\.local\bin\platform-tools\adb.exe',
                '-s', '127.0.0.1:16384', 'forward', 'tcp:27042', 'tcp:27042'
            ], check=True, capture_output=True)
            device = frida.get_device_manager().add_remote_device('127.0.0.1:27042')
            print(f"[OK] 远程设备: {device.id} ({device.name})")
        except Exception as e2:
            print(f"[!] 远程连接也失败: {e2}")
            return

    # 附加进程
    print(f"\n[3] 附加到进程 {pid} ({name})...")
    try:
        session = device.attach(int(pid))
        print(f"[OK] 附加成功")
    except Exception as e:
        print(f"[!] attach 失败: {e}")
        return

    # 创建脚本
    print(f"\n[4] 注入 SSL Unpinning 脚本...")
    script = session.create_script(FRIDA_SCRIPT)
    script.on('message', on_message)
    script.load()

    print("\n" + "=" * 60)
    print("  [OK] SSL Unpinning 已激活！")
    print("  [OK] 现在游戏 HTTPS 流量会被 mitmdump 解密")
    print("  [OK] 打开战报页面，mitmdump 会自动捕获接口")
    print("=" * 60)
    print("\n按 Ctrl+C 退出\n")

    # 保持运行
    sys.stdin.read()

if __name__ == '__main__':
    main()
