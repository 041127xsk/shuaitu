import frida
import time

# 连接设备
device = frida.get_device_manager().add_remote_device('127.0.0.1:27042')
print('Connected:', device.name)

# 使用 spawn 启动游戏
print('Spawning game...')
pid = device.spawn(['com.netease.stzb.uc'])
print('Spawned PID:', pid)

# 附加到进程
session = device.attach(pid)
print('Attached')

# 加载 SSL Unpinning 脚本
script = session.create_script("""
Java.perform(function () {
    var TAG = "[SSL-Unpin]";
    
    // TrustManagerImpl
    try {
        var tmi = Java.use('com.android.org.conscrypt.TrustManagerImpl');
        tmi.checkServerTrusted.overload('[Ljava.security.cert.X509Certificate;', 'java.lang.String', 'java.lang.String').implementation = function (chain, authType, host) {
            send(TAG + " TrustManagerImpl: bypass for " + host);
            return;
        };
        send(TAG + " TrustManagerImpl hook applied");
    } catch (e) { send(TAG + " TrustManagerImpl not found: " + e); }
    
    send(TAG + " SSL unpinning active!");
});
""")

def on_message(message, data):
    if message['type'] == 'send':
        print('[Frida]', message['payload'])
    elif message['type'] == 'error':
        print('[Frida Error]', message['stack'])

script.on('message', on_message)
script.load()
print('Script loaded')

# 恢复进程
device.resume(pid)
print('Game resumed')

# 保持运行
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print('Stopping...')
    session.detach()
    device.kill(pid)
