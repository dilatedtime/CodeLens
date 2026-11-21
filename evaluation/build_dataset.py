"""Author-owned synthetic examples. No submitted or fixture code is executed."""
import json
from pathlib import Path

# Each positive has a negative control. Labels are hypotheses for human review;
# exact semantics and additional findings must be adjudicated before publication.
PAIRS = [
('mutable-list','bug',1,3,'Mutable default shares state across calls.',
 'def add(item, values=[]):\n    values.append(item)\n    return values\n',
 'def add(item, values=None):\n    if values is None:\n        values = []\n    values.append(item)\n    return values\n'),
('mutable-dict','bug',1,3,'Mutable dictionary persists across calls.',
 'def remember(key, value, store={}):\n    store[key] = value\n    return store\n',
 'def remember(key, value, store=None):\n    if store is None:\n        store = {}\n    store[key] = value\n    return store\n'),
('off-by-one','bug',2,3,'Loop accesses one element past the end.',
 'def total(values):\n    return sum(values[i] for i in range(len(values) + 1))\n',
 'def total(values):\n    return sum(values)\n'),
('empty-average','bug',2,2,'Division by zero for an empty input.',
 'def average(values):\n    return sum(values) / len(values)\n',
 'def average(values):\n    if not values:\n        raise ValueError("At least one value required")\n    return sum(values) / len(values)\n'),
('missing-return','bug',2,3,'Positive inputs implicitly return None.',
 'def magnitude(value):\n    if value < 0:\n        return -value\n',
 'def magnitude(value):\n    if value < 0:\n        return -value\n    return value\n'),
('always-true','bug',2,3,'Nonempty string makes the condition always true.',
 'def supported(kind):\n    if kind == "csv" or "json":\n        return True\n    return False\n',
 'def supported(kind):\n    return kind in {"csv", "json"}\n'),
('shell-injection','security',3,3,'Untrusted command text is interpreted by a shell.',
 'import subprocess\ndef list_directory(path):\n    return subprocess.check_output("ls " + path, shell=True)\n',
 'from pathlib import Path\ndef list_directory(path):\n    return [item.name for item in Path(path).iterdir()]\n'),
('eval-input','security',2,2,'Untrusted expressions execute arbitrary Python.',
 'def parse_number(text):\n    return eval(text)\n',
 'def parse_number(text):\n    return float(text)\n'),
('sql-injection','security',2,2,'Name is interpolated into SQL.',
 'def find_user(connection, name):\n    return connection.execute("SELECT * FROM users WHERE name = \'" + name + "\'").fetchall()\n',
 'def find_user(connection, name):\n    return connection.execute("SELECT * FROM users WHERE name = ?", (name,)).fetchall()\n'),
('file-lifetime','maintainability',2,3,'File is not explicitly closed.',
 'def read_text(path):\n    handle = open(path, encoding="utf-8")\n    return handle.read()\n',
 'def read_text(path):\n    with open(path, encoding="utf-8") as handle:\n        return handle.read()\n'),
('quadratic-membership','performance',2,5,'List membership creates quadratic behavior for hashable inputs.',
 'def unique(values):\n    result = []\n    for value in values:\n        if value not in result:\n            result.append(value)\n    return result\n',
 'def unique(values):\n    """Return unique hashable values in insertion order."""\n    return list(dict.fromkeys(values))\n'),
('late-binding','bug',2,2,'All closures capture the final loop value.',
 'def multipliers():\n    return [lambda x: x * i for i in range(5)]\n',
 'def multipliers():\n    return [lambda x, factor=i: x * factor for i in range(5)]\n'),
('mutate-iteration','bug',2,4,'Removing elements while iterating skips adjacent negatives.',
 'def remove_negative(values):\n    for value in values:\n        if value < 0:\n            values.remove(value)\n    return values\n',
 'def remove_negative(values):\n    return [value for value in values if value >= 0]\n'),
('wrong-sort-return','bug',2,2,'list.sort returns None, not the sorted list.',
 'def ordered(values):\n    return values.sort()\n',
 'def ordered(values):\n    return sorted(values)\n'),
('zero-step','bug',2,2,'Explicit zero range step raises ValueError.',
 'def indexes(length):\n    return list(range(0, length, 0))\n',
 'def indexes(length):\n    return list(range(length))\n'),
('negative-max','bug',2,5,'Initial zero produces the wrong maximum for all-negative inputs.',
 'def maximum(values):\n    best = 0\n    for value in values:\n        if value > best:\n            best = value\n    return best\n',
 'def maximum(values):\n    if not values:\n        raise ValueError("At least one value required")\n    return max(values)\n'),
]


def build():
    examples=[]
    for i,(name,category,start,end,reason,buggy,clean) in enumerate(PAIRS):
        split='holdout' if i % 4 == 3 else 'development'
        for is_bug,code in [(True,buggy),(False,clean)]:
            examples.append({'id':name+('-bug' if is_bug else '-clean'),'split':split,'files':{'main.py':code},
                'labels':[{'path':'main.py','start_line':start,'end_line':min(end,len(code.splitlines())),'category':category,'issue_type':name,'rationale':reason}] if is_bug else []})
    return examples


if __name__=='__main__':
    target=Path(__file__).with_name('dataset.json')
    target.write_text(json.dumps(build(),indent=2),encoding='utf-8')
    print(f'Wrote {len(build())} examples to {target}')
