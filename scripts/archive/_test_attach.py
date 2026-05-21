import frida
import time

# 连接设备
device = frida.get_usb_device(timeout=5)
print('Connected:', device.name)

# 查找游戏进程
processes = device.enumerate_processes()
for p in processes:
    if 'stzb' in p.name.lower():
        print(f'Found: PID={p.pid}, Name={p.name}')

# 尝试附加到 com.netease.stzb.uc
try:
    target = 'com.netease.stzb.uc'
    session = device.attach(target)
    print(f'Successfully attached to {target}')
    
    # 加载简单脚本
    script = session.create_script("""
    Java.perform(function() {
        send("SSL Unpinning active!");
    });
    """)
    
    def on_message(msg, data):
        if msg['type'] == 'send':
            print('[Frida]', msg['payload'])
    
    script.on('message', on_message)
    script.load()
    print('Script loaded successfully')
    
    # 保持运行
    time.sleep(2)
    session.detach()
    print('Detached')
    
except Exception as e:
    print(f'Error: {e}')
