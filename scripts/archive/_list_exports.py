"""扫描 libhp12_x86_64.so 的导出符号"""
import frida, time

pid = 4568
device = frida.get_usb_device(timeout=5)
session = device.attach(pid)

script = session.create_script("""
var mod = Process.findModuleByName('libhp12_x86_64.so');
if (!mod) {
    send({type: 'error', msg: 'libhp12_x86_64.so not found'});
} else {
    var exports = mod.enumerateExports();
    var netFuncs = [];
    var allNames = [];
    for (var i = 0; i < exports.length; i++) {
        var e = exports[i];
        allNames.push(e.name);
        var lower = e.name.toLowerCase();
        if (lower.indexOf('send') !== -1 || lower.indexOf('recv') !== -1 ||
            lower.indexOf('connect') !== -1 || lower.indexOf('socket') !== -1 ||
            lower.indexOf('read') !== -1 || lower.indexOf('write') !== -1 ||
            lower.indexOf('ssl') !== -1 || lower.indexOf('tcp') !== -1 ||
            lower.indexOf('http') !== -1 || lower.indexOf('net') !== -1 ||
            lower.indexOf('request') !== -1 || lower.indexOf('response') !== -1) {
            netFuncs.push(e.name + ' @ ' + e.address);
        }
    }
    send({type: 'net', count: netFuncs.length, funcs: netFuncs});
    send({type: 'all', count: allNames.length, names: allNames.slice(0, 50)});
}
""")

net_funcs = []
all_names = []

def on_message(msg, data):
    if msg['type'] == 'send':
        p = msg['payload']
        if p['type'] == 'net':
            net_funcs.extend(p['funcs'])
        elif p['type'] == 'all':
            all_names.extend(p['names'])

script.on('message', on_message)
script.load()
time.sleep(1)
session.detach()

print(f"总导出符号: {len(all_names)}")
print(f"\n前 50 个符号:")
for n in all_names:
    print(f"  {n}")

print(f"\n===== 网络相关符号 ({len(net_funcs)}) =====")
for f in net_funcs:
    print(f"  {f}")
