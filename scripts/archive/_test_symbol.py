import frida, json

device = frida.get_usb_device(timeout=3)
session = device.attach(5079)

script = session.create_script("""
    try {
        var sym1 = Module.findExportByName(null, 'SSL_CTX_set_custom_verify');
        var sym2 = Module.findExportByName('libssl.so', 'SSL_CTX_set_custom_verify');
        
        var mods = Process.enumerateModules();
        var sslMod = mods.find(function(m) { return m.name === 'libssl.so'; });
        var exports = sslMod.enumerateExports();
        var found = exports.find(function(e) { return e.name === 'SSL_CTX_set_custom_verify'; });
        
        send({
            byNull: sym1 ? sym1.toString() : null,
            byName: sym2 ? sym2.toString() : null,
            byEnum: found ? {name: found.name, address: found.address.toString()} : null,
        });
    } catch(e) {
        send({error: e.message});
    }
""")

def on_message(message, data):
    if message['type'] == 'send':
        print(json.dumps(message.get('payload'), indent=2))
    else:
        print('ERR:', message)

script.on('message', on_message)
script.load()

import time
time.sleep(2)
session.detach()
