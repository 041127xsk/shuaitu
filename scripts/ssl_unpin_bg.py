"""
ssl_unpin_bg.py - Frida SSL Unpinning 后台运行版
================================================
注入 SSL Unpinning 脚本后保持运行，不阻塞终端。
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import frida
import subprocess

ADB = r"C:\Users\27557\.local\bin\platform-tools\adb.exe"
SERIAL = "127.0.0.1:16384"


def get_stzb_process():
    """查找率土之滨进程"""
    r = subprocess.run(
        [ADB, "-s", SERIAL, "shell", "ps -A | grep -iE 'stz|stzb|sango|netease'"],
        capture_output=True, text=True, timeout=10
    )
    lines = [l for l in r.stdout.strip().split('\n') if l]
    candidates = []
    for line in lines:
        parts = line.split()
        if len(parts) >= 9:
            pid = parts[1]
            name = parts[-1]
            state = ''
            for i, p in enumerate(parts):
                if p in ['R', 'S', 'D', 'Z', 'T', 't', 'X', 'x', 'K', 'W']:
                    state = p
                    break
            if state == 'Z':
                continue
            if 'stzb' in name.lower() or 'stz' in name.lower():
                candidates.append((pid, name))
    for pid, name in candidates:
        if name == 'com.netease.stzb.uc':
            return pid, name
    if candidates:
        return candidates[0]
    return None, None


FRIDA_SCRIPT = r"""
(function () {
    var TAG = "[SSL-Unpin]";
    var hookCount = 0;

    function log(msg) { send(TAG + " " + msg); }

    function tryHook(name, fn) {
        try { fn(); hookCount++; log("[OK] " + name); }
        catch (e) { log("[SKIP] " + name + ": " + e.message); }
    }

    function findExportAddr(moduleName, exportName) {
        var mods = Process.enumerateModules();
        var mod = mods.find(function(m) { return m.name === moduleName; });
        if (!mod) throw new Error("module not found: " + moduleName);
        var exports = mod.enumerateExports();
        var found = exports.find(function(e) { return e.name === exportName; });
        if (!found) throw new Error("export not found: " + exportName);
        return found.address;
    }

    tryHook("SSL_CTX_set_custom_verify", function () {
        var addr = findExportAddr("libssl.so", "SSL_CTX_set_custom_verify");
        Interceptor.attach(addr, {
            onEnter: function (args) {
                var callbackPtr = args[2];
                if (callbackPtr.isNull()) return;
                var nop = new NativeCallback(function () { return 0; }, 'int', []);
                args[2] = nop;
            }
        });
    });

    tryHook("SSL_set_verify", function () {
        var addr = findExportAddr("libssl.so", "SSL_set_verify");
        Interceptor.attach(addr, {
            onEnter: function (args) { args[1] = ptr(0x00); }
        });
    });

    tryHook("X509_verify_cert", function () {
        var addr = findExportAddr("libssl.so", "X509_verify_cert");
        Interceptor.replace(addr, new NativeCallback(function () {
            return 1;
        }, 'int', ['pointer']));
    });

    tryHook("SSL_CTX_set_verify", function () {
        var addr = findExportAddr("libssl.so", "SSL_CTX_set_verify");
        Interceptor.attach(addr, {
            onEnter: function (args) { args[1] = ptr(0x00); }
        });
    });

    tryHook("SSL_set_custom_verify", function () {
        var addr = findExportAddr("libssl.so", "SSL_set_custom_verify");
        Interceptor.attach(addr, {
            onEnter: function (args) {
                var callbackPtr = args[2];
                if (callbackPtr.isNull()) return;
                var nop = new NativeCallback(function () { return 0; }, 'int', []);
                args[2] = nop;
            }
        });
    });

    if (typeof Java !== 'undefined') {
        Java.perform(function () {
            tryHook("OkHttp3", function () {
                var v = Java.use('okhttp3.internal.tls.OkHostnameVerifier');
                v.verify.overload('java.lang.String', 'javax.net.ssl.SSLSession').implementation = function () { return true; };
            });
            tryHook("TrustManagerImpl", function () {
                var tmi = Java.use('com.android.org.conscrypt.TrustManagerImpl');
                tmi.checkServerTrusted.overload('[Ljava.security.cert.X509Certificate;', 'java.lang.String', 'java.lang.String').implementation = function () {};
            });
            tryHook("WebViewClient", function () {
                var WVC = Java.use('android.webkit.WebViewClient');
                WVC.onReceivedSslError.overload('android.webkit.WebView', 'android.webkit.SslErrorHandler', 'android.net.http.SslError').implementation = function (view, handler) { handler.proceed(); };
            });
        });
    }

    log("Completed. Active hooks: " + hookCount);
})();
"""


def on_message(message, data):
    if message['type'] == 'send':
        print(f"[Frida] {message['payload']}")
    elif message['type'] == 'error':
        print(f"[Frida Error] {message['stack']}")


def main():
    print("=" * 50)
    print("  SSL Unpinning (background)")
    print("=" * 50)

    print("\n[1] Finding game process...")
    pid, name = get_stzb_process()
    if not pid:
        print("[!] Game process not found! Start the game first.")
        return
    print(f"[OK] PID={pid}, Name={name}")

    print("\n[2] Connecting to frida-server...")
    try:
        device = frida.get_usb_device(timeout=5)
        print(f"[OK] USB: {device.name}")
    except Exception:
        subprocess.run([ADB, "-s", SERIAL, "forward", "tcp:27042", "tcp:27042"],
                       capture_output=True, timeout=5)
        device = frida.get_device_manager().add_remote_device('127.0.0.1:27042')
        print(f"[OK] Remote: {device.name}")

    print(f"\n[3] Attaching to {pid}...")
    session = device.attach(int(pid))
    print("[OK] Attached")

    print("\n[4] Injecting SSL Unpinning...")
    script = session.create_script(FRIDA_SCRIPT)
    script.on('message', on_message)
    script.load()

    print("\n" + "=" * 50)
    print("  [OK] SSL Unpinning ACTIVE")
    print("  [OK] HTTPS traffic will be decrypted by mitmdump")
    print("=" * 50)
    print("\nPress Ctrl+C to stop\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
        session.detach()


if __name__ == '__main__':
    main()
