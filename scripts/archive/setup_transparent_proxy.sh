#!/system/bin/sh
# 透明代理：将所有 443 流量重定向到本地 8090 端口
# 用法：adb shell su -c 'sh /data/local/tmp/setup_proxy.sh'

PROXY_PORT=8090

# 清除旧规则
iptables -t nat -F OUTPUT
iptables -t nat -F PREROUTING

# 将本机发出的 443 流量重定向到本地 PROXY_PORT
# 排除 frida-server 和 mitmdump 自己的流量（避免循环）
iptables -t nat -A OUTPUT -p tcp --dport 443 -m owner ! --uid-owner root -j REDIRECT --to-port $PROXY_PORT

# 将 80 流量也重定向
iptables -t nat -A OUTPUT -p tcp --dport 80 -m owner ! --uid-owner root -j REDIRECT --to-port $PROXY_PORT

echo "Transparent proxy enabled: 80/443 -> $PROXY_PORT"
