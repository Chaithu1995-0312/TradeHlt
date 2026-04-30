import os
import glob

BOM = b'\xef\xbb\xbf'

fixed_count = 0
for fname in glob.glob('**/*.py', recursive=True):
    try:
        with open(fname, 'rb') as f:
            data = f.read()
        if data.startswith(BOM):
            print(f"Fixing BOM in {fname}")
            with open(fname, 'wb') as f:
                f.write(data[len(BOM):])
            fixed_count += 1
    except Exception as e:
        print(f"Error processing {fname}: {e}")

print(f"Fixed {fixed_count} files with UTF-8 BOM")