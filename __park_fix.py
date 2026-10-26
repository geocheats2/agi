import ast, sys

f = r'c:\Users\George\GoogleDrive\my-projects\agi\tests\unit\test_phase2_delegation.py'
t = open(f, encoding='utf-8').read().replace('\r\n', '\n')

old = (
    '    # Operator finishes the child (its remaining generic steps are\n'
    '    # work/verify); the next run_task WAKES the parent, consolidates the\n'
    '    # child output, and completes.\n'
    '    rt._run_step(rt.task(child_id), "work")\n'
    '    rt._run_step(rt.task(child_id), "verify")\n'
    '    assert rt.task(child_id).status == "completed"\n'
)
new = (
    '    # Operator finishes the child through the real run path (its\n'
    '    # remaining generic steps are work/verify). Completing it roll-ups\n'
    '    # its spend and WAKES the parked parent.\n'
    '    assert rt.run_task(child_id).status == "completed"\n'
)
n = t.count(old)
print('matches:', n)
if n != 1:
    sys.exit(1)
t = t.replace(old, new)
ast.parse(t)
open(f, 'w', encoding='utf-8', newline='\r\n').write(t)
print('park test fixed')
