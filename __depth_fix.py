import ast
f = r'c:\Users\George\GoogleDrive\my-projects\agi\src\csa\runtime.py'
t = open(f, encoding='utf-8').read().replace('\r\n', '\n')
old = (
    '            if not row:\n'
    '                break\n'
    '            cur = row["parent_task_id"]\n'
    '            depth += 1\n'
)
new = (
    '            if not row or row["parent_task_id"] is None:\n'
    '                break\n'
    '            cur = row["parent_task_id"]\n'
    '            depth += 1\n'
)
n = t.count(old)
print('matches:', n)
if n != 1:
    import sys; sys.exit(1)
t = t.replace(old, new)
ast.parse(t)
open(f, 'w', encoding='utf-8', newline='\r\n').write(t)
t2 = open(f, encoding='utf-8').read()
assert 'row["parent_task_id"] is None' in t2
print('depth_of fixed + verified on disk')