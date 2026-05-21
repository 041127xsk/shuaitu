import lzma
import os

src = r'C:\Users\27557\Downloads\frida-server-17.9.6-android-x86_64.xz'
dst = r'C:\Users\27557\Downloads\frida-server-17.9.6'

if os.path.exists(dst):
    os.remove(dst)

with lzma.open(src, 'rb') as f_in:
    with open(dst, 'wb') as f_out:
        f_out.write(f_in.read())

print("Extracted successfully")
