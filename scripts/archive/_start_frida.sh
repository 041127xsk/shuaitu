#!/system/bin/sh
pkill frida-server
sleep 1
nohup /data/local/tmp/frida-server > /data/local/tmp/frida.log 2>&1 &
