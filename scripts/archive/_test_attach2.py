import frida
import time

# 连接设备
device = frida.get_usb_device(timeout=5)
print('Connected:', device.name)

# 尝试直接附加到 PID
target_pid = 5079
try:
    session = device.attach(target_pid)
    print(f'Successfully attached to PID {target_pid}')
    
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
