"""列出游戏进程所有加载的模块，找网络相关库"""
import frida, time

pid = 4568
device = frida.get_usb_device(timeout=5)
session = device.attach(pid)

script = session.create_script("""
var mods = Process.enumerateModules();
var netMods = [];
var allMods = [];
for (var i = 0; i < mods.length; i++) {
    var m = mods[i];
    allMods.push(m.name + ' @ ' + m.base);
    var lower = m.name.toLowerCase();
    if (lower.indexOf('net') !== -1 || lower.indexOf('socket') !== -1 ||
        lower.indexOf('ssl') !== -1 || lower.indexOf('crypto') !== -1 ||
        lower.indexOf('http') !== -1 || lower.indexOf('curl') !== -1 ||
        lower.indexOf('unity') !== -1 || lower.indexOf('il2cpp') !== -1 ||
        lower.indexOf('mono') !== -1 || lower.indexOf('x86') !== -1 ||
        lower.indexOf('stzb') !== -1 || lower.indexOf('netease') !== -1) {
        netMods.push(m.name + ' @ ' + m.base + ' (size=' + m.size + ')');
    }
}
send({type: 'all', count: allMods.length, mods: allMods});
send({type: 'net', count: netMods.length, mods: netMods});
""")

all_modules = []
net_modules = []

def on_message(msg, data):
    if msg['type'] == 'send':
        p = msg['payload']
        if p['type'] == 'all':
            all_modules.extend(p['mods'])
        elif p['type'] == 'net':
            net_modules.extend(p['mods'])

script.on('message', on_message)
script.load()
time.sleep(1)
session.detach()

print(f"总计模块: {len(all_modules)}")
print(f"\n===== 网络/游戏相关模块 ({len(net_modules)}) =====")
for m in net_modules:
    print(f"  {m}")
