import ast
import json

base = r'c:\Users\George\GoogleDrive\my-projects\agi'
out = {}


def load(rel):
    with open(base + '\\' + rel, encoding='utf-8') as f:
        return f.read().replace('\r\n', '\n')


# runtime.py
rt = load('src/csa/runtime.py')
try:
    ast.parse(rt)
    out['runtime_ast'] = True
except SyntaxError as e:
    out['runtime_ast'] = f'FAIL {e}'
out['runtime_task_type_param'] = 'acceptance: list[str] | None = None,\n                      task_type: str = "generic") -> str:' in rt
out['runtime_rollup_def'] = 'def _roll_up_spend' in rt
out['runtime_rollup_calls'] = rt.count('self._roll_up_spend(task_id)')
out['runtime_spawn_var'] = 'task_type=task_type,' in rt
out['runtime_guard'] = 'a delegation task cannot be a child of' in rt

# model.py
mp = load('src/csa/model.py')
try:
    ast.parse(mp)
    out['model_ast'] = True
except SyntaxError as e:
    out['model_ast'] = f'FAIL {e}'
out['model_consumed'] = 'consumed' in mp and 'child result(s)' in mp
for line in mp.splitlines():
    if 'Authorization' in line:
        out['model_auth_line_has_api_key'] = 'api_key' in line
        out['model_auth_line_len'] = len(line)

# test file
tp = load('tests/unit/test_phase2_delegation.py')
try:
    ast.parse(tp)
    out['test_ast'] = True
except SyntaxError as e:
    out['test_ast'] = f'FAIL {e}'
out['test_child_task_type'] = 'assert child.task_type == "generic"' in tp
out['test_child_type_bad'] = 'assert child.type == "generic"' in tp
out['test_umbrella'] = 'Generic umbrella' in tp
out['test_consumed_asserts'] = tp.count('"consumed" in')
out['test_child_results_asserts'] = tp.count('"child results" in')
out['test_park_call_count_1'] = '_usage(rt, child_id)[1] == 1' in tp
out['test_collect_objectives'] = 'Collect field notes A' in tp

print(json.dumps(out, indent=1))
