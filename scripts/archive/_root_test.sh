#!/system/bin/sh
echo "Testing root access..."
/system/xbin/su -c "id"
echo "Exit code: $?"
