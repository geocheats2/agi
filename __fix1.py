import ast

f = r'c:\Users\George\GoogleDrive\my-projects\agi\tests\unit\test_phase2_delegation.py'
t = open(f, encoding='utf-8').read().replace('\r\n', '\n')

old = '''        {"objective": "Collect field notes A", "acceptance": ["covers A"]},
        {"objective": "Collect field notes B", "acceptance": ["covers B"]},
    ])
'''
new = '''        {"objective": "Gather field notes from site A", "acceptance": ["covers A"]},
        {"objective": "Gather field notes from site B", "acceptance": ["covers B"]},
    ])
'''
n = t.count(old)
print('match1:', n)
if n == 1:
    t = t.replace(old, new)

old2 = 'assert [c.objective for c in children] == ["Collect field notes A",\n                                               "Collect field notes B"]'
new2 = 'assert [c.objective for c in children] == ["Gather field notes from site A",\n                                               "Gather field notes from site B"]'
n2 = t.count(old2)
print('match2:', n2)
if n2 == 1:
    t = t.replace(old2, new2)

ast.parse(t)
open(f, 'w', encoding='utf-8', newline='\r\n').write(t)
print('ok')
