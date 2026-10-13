# Build: python3 build.py  -> dist/ez.tank_picker_<ver>.wotmod (compiles with python2.7)
import os, re, subprocess, sys, zipfile
root = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(root, 'src')
ver = re.search(r'<version>(.*?)</version>', open(os.path.join(src, 'meta.xml')).read()).group(1)
py = 'res/scripts/client/gui/mods/mod_advances_picker.py'
subprocess.check_call(['python2.7', '-c', 'import py_compile,sys; py_compile.compile(sys.argv[1], cfile=sys.argv[2], dfile=sys.argv[3], doraise=True)',
                       os.path.join(src, py), os.path.join(src, py + 'c'), 'scripts/client/gui/mods/mod_advances_picker.py'])
os.makedirs(os.path.join(root, 'dist'), exist_ok=True)
out = os.path.join(root, 'dist', 'ez.tank_picker_%s.wotmod' % ver)
with zipfile.ZipFile(out, 'w', zipfile.ZIP_STORED) as z:
    z.write(os.path.join(src, 'meta.xml'), 'meta.xml')
    for d in ('res/', 'res/scripts/', 'res/scripts/client/', 'res/scripts/client/gui/', 'res/scripts/client/gui/mods/'):
        z.writestr(zipfile.ZipInfo(d), b'')
    z.write(os.path.join(src, py + 'c'), py + 'c')
print(out)
