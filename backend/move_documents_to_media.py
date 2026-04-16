import os
import shutil

root = r'C:\Users\balsa\lastversion\backend'
old = os.path.join(root, 'documents')
new = os.path.join(root, 'media', 'documents')
if os.path.exists(old):
    os.makedirs(new, exist_ok=True)
    for dirpath, dirnames, filenames in os.walk(old):
        rel = os.path.relpath(dirpath, old)
        target_dir = os.path.join(new, rel) if rel != '.' else new
        os.makedirs(target_dir, exist_ok=True)
        for fname in filenames:
            src = os.path.join(dirpath, fname)
            dst = os.path.join(target_dir, fname)
            print('move', src, '->', dst)
            shutil.move(src, dst)
    for dirpath, dirnames, filenames in os.walk(old, topdown=False):
        if not os.listdir(dirpath):
            os.rmdir(dirpath)
            print('rmdir', dirpath)
else:
    print('old path missing', old)
print('media exists', os.path.exists(os.path.join(root, 'media')))
