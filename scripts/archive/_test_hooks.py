"""测试各种 IO 函数是否能 hook 到数据"""
import frida, time, sys
from datetime import datetime

pid = 4568
device = frida.get_usb_device(timeout=5)
session = device.attach(pid)

FRIDA_JS = '''
function findModule(name) {
    var m = Process.findModuleByName(name);
    if (m) return m;
    var mods = Process.enumerateModules();
    return mods.find(function(mod) { return mod.name.indexOf(name) !== -1; });
}

function findExport(mod, name) {
    if (!mod) return null;
    var exports = mod.enumerateExports();
    return exports.find(function(e) { return e.name === name; });
}

function tryHook(modName, funcName, handler) {
    var mod = findModule(modName);
    if (!mod) return;
    var exp = findExport(mod, funcName);
    if (!exp) return;
    Interceptor.attach(exp.address, handler);
    send({type: 'info', msg: funcName + '() hooked'});
}

var hitCount = {};
function recordHit(name) {
    hitCount[name] = (hitCount[name] || 0) + 1;
}

// libc socket/IO
tryHook("libc.so", "send", {
    onEnter: function(args) {
        recordHit('send');
        var len = args[2].toInt32();
        if (len > 0 && len < 32768) {
            var data = Memory.readByteArray(args[1], Math.min(len, 256));
            send({type: 'hit', func: 'send', len: len}, data);
        }
    }
});

tryHook("libc.so", "sendto", {
    onEnter: function(args) {
        recordHit('sendto');
        var len = args[2].toInt32();
        if (len > 0 && len < 32768) {
            var data = Memory.readByteArray(args[1], Math.min(len, 256));
            send({type: 'hit', func: 'sendto', len: len}, data);
        }
    }
});

tryHook("libc.so", "sendmsg", {
    onEnter: function(args) {
        recordHit('sendmsg');
        send({type: 'hit', func: 'sendmsg', len: 0});
    }
});

tryHook("libc.so", "recv", {
    onEnter: function(args) { this.buf = args[1]; },
    onLeave: function(retval) {
        recordHit('recv');
        var ret = retval.toInt32();
        if (ret > 0 && ret < 32768 && this.buf) {
            var data = Memory.readByteArray(this.buf, Math.min(ret, 256));
            send({type: 'hit', func: 'recv', len: ret}, data);
        }
    }
});

tryHook("libc.so", "recvfrom", {
    onEnter: function(args) { this.buf = args[1]; },
    onLeave: function(retval) {
        recordHit('recvfrom');
        var ret = retval.toInt32();
        if (ret > 0 && ret < 32768 && this.buf) {
            var data = Memory.readByteArray(this.buf, Math.min(ret, 256));
            send({type: 'hit', func: 'recvfrom', len: ret}, data);
        }
    }
});

tryHook("libc.so", "recvmsg", {
    onEnter: function(args) { this.buf = args[1]; },
    onLeave: function(retval) {
        recordHit('recvmsg');
        var ret = retval.toInt32();
        if (ret > 0) {
            send({type: 'hit', func: 'recvmsg', len: ret});
        }
    }
});

tryHook("libc.so", "write", {
    onEnter: function(args) {
        recordHit('write');
        var len = args[2].toInt32();
        if (len > 0 && len < 32768) {
            var data = Memory.readByteArray(args[1], Math.min(len, 256));
            send({type: 'hit', func: 'write', len: len}, data);
        }
    }
});

tryHook("libc.so", "read", {
    onEnter: function(args) { this.buf = args[1]; },
    onLeave: function(retval) {
        recordHit('read');
        var ret = retval.toInt32();
        if (ret > 0 && ret < 32768 && this.buf) {
            var data = Memory.readByteArray(this.buf, Math.min(ret, 256));
            send({type: 'hit', func: 'read', len: ret}, data);
        }
    }
});

tryHook("libc.so", "writev", {
    onEnter: function(args) {
        recordHit('writev');
        send({type: 'hit', func: 'writev', len: args[2].toInt32()});
    }
});

tryHook("libc.so", "readv", {
    onEnter: function(args) { this.cnt = args[2].toInt32(); },
    onLeave: function(retval) {
        recordHit('readv');
        var ret = retval.toInt32();
        if (ret > 0) {
            send({type: 'hit', func: 'readv', len: ret});
        }
    }
});

tryHook("libc.so", "pread", {
    onEnter: function(args) { this.buf = args[1]; },
    onLeave: function(retval) {
        recordHit('pread');
        var ret = retval.toInt32();
        if (ret > 0 && ret < 32768 && this.buf) {
            var data = Memory.readByteArray(this.buf, Math.min(ret, 256));
            send({type: 'hit', func: 'pread', len: ret}, data);
        }
    }
});

tryHook("libc.so", "pwrite", {
    onEnter: function(args) {
        recordHit('pwrite');
        var len = args[2].toInt32();
        if (len > 0 && len < 32768) {
            var data = Memory.readByteArray(args[1], Math.min(len, 256));
            send({type: 'hit', func: 'pwrite', len: len}, data);
        }
    }
});

// libssl
tryHook("libssl.so", "SSL_write", {
    onEnter: function(args) {
        recordHit('SSL_write');
        var len = args[2].toInt32();
        if (len > 0 && len < 32768) {
            var data = Memory.readByteArray(args[1], Math.min(len, 256));
            send({type: 'hit', func: 'SSL_write', len: len}, data);
        }
    }
});

tryHook("libssl.so", "SSL_read", {
    onEnter: function(args) { this.buf = args[1]; },
    onLeave: function(retval) {
        recordHit('SSL_read');
        var ret = retval.toInt32();
        if (ret > 0 && ret < 32768 && this.buf) {
            var data = Memory.readByteArray(this.buf, Math.min(ret, 256));
            send({type: 'hit', func: 'SSL_read', len: ret}, data);
        }
    }
});

// epoll_wait - 监控是否有事件触发
tryHook("libc.so", "epoll_wait", {
    onEnter: function(args) { this.timeout = args[3].toInt32(); },
    onLeave: function(retval) {
        var ret = retval.toInt32();
        if (ret > 0) {
            recordHit('epoll_wait');
            // 只在有事件时发送，避免刷屏
            if ((hitCount['epoll_wait'] || 0) % 50 === 1) {
                send({type: 'hit', func: 'epoll_wait', len: ret});
            }
        }
    }
});

// connect
tryHook("libc.so", "connect", {
    onEnter: function(args) {
        var sockaddr = args[1];
        var family = Memory.readU16(sockaddr);
        if (family === 2) {
            var port = Memory.readU16(sockaddr.add(2));
            port = ((port & 0xFF) << 8) | ((port >> 8) & 0xFF);
            var ip = [];
            for (var i = 0; i < 4; i++) ip.push(Memory.readU8(sockaddr.add(4 + i)));
            send({type: 'connect', addr: ip.join('.') + ':' + port});
        }
    }
});

send({type: 'ready', msg: 'All hooks active. Operate on emulator now.'});
'''

script = session.create_script(FRIDA_JS)

stats = {}

def on_message(msg, data):
    if msg['type'] != 'send':
        return
    p = msg['payload']
    if p.get('type') == 'hit':
        func = p['func']
        stats[func] = stats.get(func, 0) + 1
        if data:
            try:
                preview = data.decode('utf-8', errors='ignore')[:80].replace('\n', ' ')
                if preview.strip():
                    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    print(f"[{ts}] [{func:12}] {p.get('len', 0):5}b | {preview}")
            except:
                pass
    elif p.get('type') == 'connect':
        print(f"[CONNECT] {p['addr']}")
    elif p.get('type') == 'info':
        print(f"[INFO] {p['msg']}")

script.on('message', on_message)
script.load()

print("[OK] Hooks 已注入。请在模拟器上操作（点击详情/刷新/翻页）")
print("[INFO] 监控 20 秒...\n")

try:
    time.sleep(20)
except KeyboardInterrupt:
    pass

session.detach()

print(f"\n===== 20 秒统计 =====")
for k, v in sorted(stats.items(), key=lambda x: -x[1]):
    print(f"  {k:15}: {v:6} 次")

if not stats:
    print("  [无数据] 未捕获到任何 IO 活动")
