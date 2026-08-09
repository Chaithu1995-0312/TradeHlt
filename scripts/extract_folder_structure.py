import os
import fnmatch

exclude_dirs = {'__pycache__', '.git', 'venv', '.venv', 'node_modules', '.egg-info', '__init__'}
exclude_patterns = ['*.pyc', '*.pyo', '*.egg-info']

root = r'd:\Tradelatest'
output_file = r'd:\Tradelatest\folder_structure_clean.txt'

with open(output_file, 'w', encoding='utf-8') as f:
    for dirpath, dirnames, filenames in os.walk(root):
        # Filter out excluded directories
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs and not any(fnmatch.fnmatch(d, p) for p in exclude_patterns)]
        
        # Get relative path
        rel_path = os.path.relpath(dirpath, root)
        if rel_path == '.':
            depth = 0
        else:
            depth = rel_path.count(os.sep) + 1
        
        indent = '  ' * depth
        dirname = os.path.basename(dirpath) if depth > 0 else 'Tradelatest'
        f.write(f'{indent}{dirname}/\n')
        
        # Write files (filter out excluded extension files)
        for filename in sorted(filenames):
            if not any(fnmatch.fnmatch(filename, p) for p in exclude_patterns):
                file_indent = '  ' * (depth + 1)
                f.write(f'{file_indent}{filename}\n')

print('Done. Output written to folder_structure_clean.txt')