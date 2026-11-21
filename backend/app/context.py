import ast
import json


def source_index(path, source):
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError) as exc:
        return {'path': path, 'symbols': [], 'imports': [], 'syntax_error': str(exc)}
    symbols = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.append({'name': node.name, 'start': min([node.lineno] + [d.lineno for d in node.decorator_list]), 'end': node.end_lineno,
                            'signature': f'{node.name}({ast.unparse(node.args)})' if hasattr(node, 'args') else node.name})
    return {'path': path, 'symbols': symbols, 'imports': [ast.unparse(n) for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))], 'syntax_error': None}


def build_context(files, budget, target=None, symbol=None):
    """Select complete AST top-level units; never silently cut a source line."""
    units, omitted, selected = [], [], []
    for path, source in sorted(files.items(), key=lambda x: (x[0] != target, x[0])):
        lines = source.splitlines()
        index = source_index(path, source)
        try:
            body = ast.parse(source).body
            ranges = [(min([n.lineno] + [d.lineno for d in getattr(n, 'decorator_list', [])]), n.end_lineno, getattr(n, 'name', ''), isinstance(n, (ast.Import, ast.ImportFrom))) for n in body]
        except (SyntaxError, ValueError, RecursionError):
            ranges = [(1, len(lines), '', False)] if lines else []
        # Whole file when it fits preserves comments and all source context.
        whole = {'path': path, 'start_line': 1, 'end_line': len(lines), 'code': source, 'index': index}
        if len(json.dumps(whole)) <= budget and not symbol:
            units.append((0 if path == target else 2, whole))
        else:
            for start, end, name, is_import in ranges:
                priority = 0 if path == target and name == symbol else (1 if is_import else 2)
                units.append((priority, {'path': path, 'start_line': start, 'end_line': end, 'code': '\n'.join(lines[start-1:end])}))
    used = 2
    for _, unit in sorted(units, key=lambda u: u[0]):
        size = len(json.dumps(unit)) + 2
        if used + size <= budget:
            selected.append(unit)
            used += size
        else:
            omitted.append({'path': unit['path'], 'start_line': unit['start_line'], 'end_line': unit['end_line']})
    included = {(u['path'], line) for u in selected for line in range(u['start_line'], u['end_line'] + 1)}
    total = sum(len(s.splitlines()) for s in files.values())
    coverage = {'included_lines': len(included), 'total_lines': total, 'omitted_units': omitted,
                'complete': len(included) == total, 'budget_chars': budget, 'used_chars': used,
                'note': 'Character budget, not an exact token count. Comments outside selected AST units may be omitted.'}
    return json.dumps(selected, ensure_ascii=True), coverage
