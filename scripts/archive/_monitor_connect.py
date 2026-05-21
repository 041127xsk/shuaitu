import frida, sys, json, time

device = frida.get_usb_device(timeout=3)
session = device.attach(3207)

script = session.create_script("""
    var TAG = "[NET]";
    
    // Hook libc connect()
    var connectPtr = Module.findExportByName(null, "connect");
    if (!connectPtr) {
        // 尝试通过 enumerateExports 查找
        var mods = Process.enumerateModules();
        var libc = mods.find(function(m) { return m.name.indexOf('libc.so') !== -1; });
        if (libc) {
            var exports = libc.enumerateExports();
            var found = exports.find(function(e) { return e.name === 'connect'; });
            if (found) connectPtr = found.address;
        }
    }
    
    if (connectPtr) {
        Interceptor.attach(connectPtr, {
            onEnter: function(args) {
                var sockaddr = args[1];
                var family = Memory.readU16(sockaddr);
                
                if (family === 2) { // AF_INET
                    var port = Memory.readU16(sockaddr.add(2));
                    port = ((port & 0xFF) << 8) | ((port >> 8) & 0xFF); // ntohs
                    var ip = [];
                    for (var i = 0; i < 4; i++) {
                        ip.push(Memory.readU8(sockaddr.add(4 + i)));
                    }
                    var addr = ip.join('.') + ':' + port;
                    send({type: 'connect', addr: addr});
                } else if (family === 10) { // AF_INET6
                    var port = Memory.readU16(sockaddr.add(2));
                    port = ((port & 0xFF) << 8) | ((port >> 8) & 0xFF);
                    send({type: 'connect', addr: '[IPv6]:' + port});
                }
            }
        });
        send({type: 'info', msg: 'connect() hooked at ' + connectPtr});
    } else {
        send({type: 'error', msg: 'connect() not found'});
    }
    
    // 同时 hook send() 来捕获发送的数据
    var sendPtr = Module.findExportByName(null, "send");
    if (!sendPtr) {
        var mods = Process.enumerateModules();
        var libc = mods.find(function(m) { return m.name.indexOf('libc.so') !== -1; });
        if (libc) {
            var exports = libc.enumerateExports();
            var found = exports.find(function(e) { return e.name === 'send'; });
            if (found) sendPtr = found.address;
        }
    }
    
    if (sendPtr) {
        Interceptor.attach(sendPtr, {
            onEnter: function(args) {
                var len = args[2].toInt32();
                if (len > 0 && len < 4096) {
                    var data = Memory.readByteArray(args[1], len);
                    send({type: 'send', len: len, data: data});
                }
            }
        });
        send({type: 'info', msg: 'send() hooked'});
    }
""")

connections = []
def on_message(message, data):
    if message['type'] == 'send':
        payload = message['payload']
        if payload.get('type') == 'connect':
            addr = payload['addr']
            if addr not in connections:
                connections.append(addr)
                print(f"[CONNECT] {addr}")
        elif payload.get('type') == 'send':
            # 尝试解码为字符串
            try:
                text = data.decode('utf-8', errors='ignore')[:200]
                if text.strip():
                    print(f"[SEND] {text[:100]}")
            except:
                pass
        else:
            print(f"[INFO] {payload.get('msg', '')}")

script.on('message', on_message)
script.load()

print("=" * 50)
print("网络连接监控已启动")
print("请在模拟器里操作战报页面...")
print("按 Ctrl+C 停止")
print("=" * 50)

try:
    time.sleep(30)
except KeyboardInterrupt:
    pass

print(f"\n捕获到的连接 ({len(connections)} 个):")
for c in connections:
    print(f"  {c}")

session.detach()
