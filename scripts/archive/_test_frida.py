import frida

device = frida.get_device_manager().add_remote_device('127.0.0.1:27042')
print('Connected:', device.name)

# 尝试附加到 PushService
session = device.attach(4223)
print('Attached to PushService')

script = session.create_script("""
Java.perform(function() {
    send("Hello from Frida");
});
""")
script.load()
print('Script loaded')
session.detach()
print('Success!')
