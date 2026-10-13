# Build: python3 build.py  -> dist/ez.tank_picker_<ver>.wotmod
# .py files under src/res are compiled with python2.7 and shipped as .pyc only.
import os, re, subprocess, zipfile
root = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(root, 'src')
ver = re.search(r'<version>(.*?)</version>', open(os.path.join(src, 'meta.xml')).read()).group(1)
os.makedirs(os.path.join(root, 'dist'), exist_ok=True)
out = os.path.join(root, 'dist', 'ez.tank_picker_%s.wotmod' % ver)
files, dirs = [], set()
for base, _, names in os.walk(os.path.join(src, 'res')):
    for name in sorted(names):
        full = os.path.join(base, name)
        rel = os.path.relpath(full, src).replace(os.sep, '/')
        if name.endswith('.pyc'):
            continue
        if name.endswith('.py'):
            dfile = rel[len('res/'):]
            subprocess.check_call(['python2.7', '-c', 'import py_compile,sys; py_compile.compile(sys.argv[1], cfile=sys.argv[2], dfile=sys.argv[3], doraise=True)', full, full + 'c', dfile])
            full, rel = full + 'c', rel + 'c'
        files.append((full, rel))
        parts = rel.split('/')[:-1]
        for i in range(1, len(parts) + 1):
            dirs.add('/'.join(parts[:i]) + '/')
with zipfile.ZipFile(out, 'w', zipfile.ZIP_STORED) as z:
    z.write(os.path.join(src, 'meta.xml'), 'meta.xml')
    for d in sorted(dirs):
        z.writestr(zipfile.ZipInfo(d), b'')
    for full, rel in files:
        z.write(full, rel)
print(out)
