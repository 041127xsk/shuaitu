import frida, json

device = frida.get_usb_device(timeout=3)
session = device.attach(5079)

script = session.create_script("""
    var mods = Process.enumerateModules();
    var sslMod = mods.find(function(m) { return m.name === 'libssl.so'; });
    var exports = sslMod.enumerateExports();
    var names = exports.map(function(e) { return e.name; });
    
    var keywords = ['verify', 'cert', 'x509', 'trust', 'pinning', 'custom'];
    var matches = names.filter(function(n) {
        var lower = n.toLowerCase();
        return keywords.some(function(k) { return lower.indexOf(k) !== -1; });
    });
    
    send({type: 'verify_symbols', matches: matches});
""")

def on_message(message, data):
    print(json.dumps(message['payload'], indent=2, ensure_ascii=False))

script.on('message', on_message)
script.load()

import time
time.sleep(2)
session.detach()
