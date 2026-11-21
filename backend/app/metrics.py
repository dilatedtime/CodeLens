"""CodeLens AST Metrics & Code Quality Engine.

Computes:
- Cyclomatic Complexity (McCabe)
- Cognitive Complexity (SonarSource spec)
- Halstead Complexity Metrics (Volume, Difficulty, Effort, Estimated Bugs)
- Maintainability Index (SEI formula)
- Static Code Smells & Security Anti-patterns (Hardcoded Secrets, Deep Nesting, God Functions)
"""

import ast
import math
import re
from typing import Any


SECRET_PATTERNS = [
    (re.compile(r'(?i)(api[_-]?key|secret|token|password|passwd|auth[_-]?token)\s*=\s*[\'"][A-Za-z0-9_\-]{16,}[\'"]'), "Hardcoded API Key or Secret Token"),
    (re.compile(r'AKIA[0-9A-Z]{16}'), "AWS Access Key ID"),
    (re.compile(r'(?i)-----BEGIN (RSA|EC|OPENSSH|PGP) PRIVATE KEY-----'), "Embedded Private Key"),
    (re.compile(r'(?i)ghp_[A-Za-z0-9]{36}'), "GitHub Personal Access Token"),
]


class CyclomaticComplexityVisitor(ast.NodeVisitor):
    """Calculates McCabe Cyclomatic Complexity for an AST node."""

    def __init__(self):
        self.complexity = 1

    def visit_If(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_IfExp(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_AsyncFor(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_With(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_AsyncWith(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_Assert(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        # Each extra boolean operand (and/or) adds a branch condition
        self.complexity += len(node.values) - 1
        self.generic_visit(node)

    def visit_comprehension(self, node):
        self.complexity += 1 + len(node.ifs)
        self.generic_visit(node)


class CognitiveComplexityVisitor(ast.NodeVisitor):
    """Calculates Cognitive Complexity (measures cognitive reading effort)."""

    def __init__(self):
        self.complexity = 0
        self.nesting_level = 0

    def _increment(self, node):
        self.complexity += 1 + self.nesting_level

    def visit_If(self, node):
        self._increment(node)
        self.nesting_level += 1
        for child in node.body:
            self.visit(child)
        self.nesting_level -= 1

        # elif / else
        orelse = node.orelse
        while orelse and len(orelse) == 1 and isinstance(orelse[0], ast.If):
            self.complexity += 1  # elif penalty
            for child in orelse[0].body:
                self.nesting_level += 1
                self.visit(child)
                self.nesting_level -= 1
            orelse = orelse[0].orelse
        if orelse:
            self.complexity += 1  # else penalty
            self.nesting_level += 1
            for child in orelse:
                self.visit(child)
            self.nesting_level -= 1

    def visit_For(self, node):
        self._increment(node)
        self.nesting_level += 1
        self.generic_visit(node)
        self.nesting_level -= 1

    def visit_While(self, node):
        self._increment(node)
        self.nesting_level += 1
        self.generic_visit(node)
        self.nesting_level -= 1

    def visit_ExceptHandler(self, node):
        self._increment(node)
        self.nesting_level += 1
        self.generic_visit(node)
        self.nesting_level -= 1


class HalsteadMetricsCalculator(ast.NodeVisitor):
    """Calculates Halstead Software Science metrics."""

    def __init__(self):
        self.operators = []
        self.operands = []

    def visit_BinOp(self, node):
        self.operators.append(type(node.op).__name__)
        self.generic_visit(node)

    def visit_UnaryOp(self, node):
        self.operators.append(type(node.op).__name__)
        self.generic_visit(node)

    def visit_Compare(self, node):
        for op in node.ops:
            self.operators.append(type(op).__name__)
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        self.operators.append(type(node.op).__name__)
        self.generic_visit(node)

    def visit_Call(self, node):
        self.operators.append('Call')
        self.generic_visit(node)

    def visit_Assign(self, node):
        self.operators.append('Assign')
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        self.operators.append(f'AugAssign_{type(node.op).__name__}')
        self.generic_visit(node)

    def visit_Name(self, node):
        self.operands.append(node.id)
        self.generic_visit(node)

    def visit_Constant(self, node):
        self.operands.append(str(node.value))
        self.generic_visit(node)


def calculate_halstead(tree: ast.AST) -> dict[str, float]:
    calculator = HalsteadMetricsCalculator()
    calculator.visit(tree)

    n1 = len(set(calculator.operators))  # distinct operators
    n2 = len(set(calculator.operands))   # distinct operands
    N1 = len(calculator.operators)        # total operators
    N2 = len(calculator.operands)         # total operands

    vocabulary = n1 + n2
    length = N1 + N2
    volume = length * math.log2(vocabulary) if vocabulary > 0 else 0.0
    difficulty = (n1 / 2.0) * (N2 / n2) if n2 > 0 else 0.0
    effort = difficulty * volume
    time_required = effort / 18.0
    bugs = volume / 3000.0

    return {
        'distinct_operators': n1,
        'distinct_operands': n2,
        'total_operators': N1,
        'total_operands': N2,
        'vocabulary': vocabulary,
        'length': length,
        'volume': round(volume, 2),
        'difficulty': round(difficulty, 2),
        'effort': round(effort, 2),
        'time_seconds': round(time_required, 2),
        'estimated_bugs': round(bugs, 4),
    }


def analyze_code_smells(source: str, tree: ast.AST, path: str) -> list[dict[str, Any]]:
    smells = []
    lines = source.splitlines()

    # Secret scanner
    for line_idx, line in enumerate(lines, start=1):
        for pattern, label in SECRET_PATTERNS:
            if pattern.search(line):
                smells.append({
                    'path': path,
                    'start_line': line_idx,
                    'end_line': line_idx,
                    'category': 'security',
                    'severity': 'critical',
                    'title': f'Potential Hardcoded Credential: {label}',
                    'explanation': f'Line {line_idx} contains a pattern matching hardcoded credentials or secrets.',
                    'evidence': line.strip(),
                    'suggested_fix': 'Store credentials in environment variables or a secure secret manager (e.g., .env or Vault).',
                    'rule_id': 'SEC001',
                    'sources': ['ast-analyzer'],
                })

    # AST-based code smells
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # 1. God Function / Too Long (> 60 lines)
            func_len = (node.end_lineno or node.lineno) - node.lineno + 1
            if func_len > 60:
                smells.append({
                    'path': path,
                    'start_line': node.lineno,
                    'end_line': node.end_lineno or node.lineno,
                    'category': 'maintainability',
                    'severity': 'medium',
                    'title': f'God Function: `{node.name}` is {func_len} lines long',
                    'explanation': f'Function `{node.name}` exceeds the recommended 60-line limit ({func_len} lines). Large functions violate the Single Responsibility Principle.',
                    'evidence': lines[node.lineno - 1].strip(),
                    'suggested_fix': 'Refactor into smaller, single-purpose helper functions.',
                    'rule_id': 'SMELL_GOD_FUNC',
                    'sources': ['ast-analyzer'],
                })

            # 2. Too Many Parameters (> 5)
            arg_count = len(node.args.args)
            if arg_count > 5:
                smells.append({
                    'path': path,
                    'start_line': node.lineno,
                    'end_line': node.lineno,
                    'category': 'maintainability',
                    'severity': 'low',
                    'title': f'Long Parameter List: `{node.name}` takes {arg_count} parameters',
                    'explanation': f'Function `{node.name}` has {arg_count} positional arguments. Long argument lists increase coupling and error rate.',
                    'evidence': lines[node.lineno - 1].strip(),
                    'suggested_fix': 'Group related arguments into a dataclass, Pydantic model, or configuration dictionary.',
                    'rule_id': 'SMELL_LONG_PARAMS',
                    'sources': ['ast-analyzer'],
                })

            # 3. Missing Docstring on public functions
            if not node.name.startswith('_') and not ast.get_docstring(node):
                smells.append({
                    'path': path,
                    'start_line': node.lineno,
                    'end_line': node.lineno,
                    'category': 'maintainability',
                    'severity': 'informational',
                    'title': f'Missing Docstring: Public function `{node.name}` lacks documentation',
                    'explanation': f'Public API function `{node.name}` does not have a docstring explaining its parameters and return values.',
                    'evidence': lines[node.lineno - 1].strip(),
                    'suggested_fix': 'Add a Google-style or Sphinx-style docstring documenting purpose, Args, and Returns.',
                    'rule_id': 'DOC001',
                    'sources': ['ast-analyzer'],
                })

        # 4. Bare except or catching generic Exception
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                smells.append({
                    'path': path,
                    'start_line': node.lineno,
                    'end_line': node.lineno,
                    'category': 'bug',
                    'severity': 'high',
                    'title': 'Bare `except:` clause catches system interrupts',
                    'explanation': 'A bare `except:` clause intercepts KeyboardInterrupt and SystemExit, preventing normal program termination.',
                    'evidence': lines[node.lineno - 1].strip(),
                    'suggested_fix': 'Catch specific exceptions (e.g., `except ValueError:`) or at least `except Exception:`.',
                    'rule_id': 'ERR001',
                    'sources': ['ast-analyzer'],
                })

        # 5. Dead Code detection (statements after terminal return/raise/break)
        if hasattr(node, 'body') and isinstance(node.body, list):
            for i, stmt in enumerate(node.body[:-1]):
                if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                    next_stmt = node.body[i + 1]
                    smells.append({
                        'path': path,
                        'start_line': next_stmt.lineno,
                        'end_line': node.body[-1].end_lineno or next_stmt.lineno,
                        'category': 'maintainability',
                        'severity': 'low',
                        'title': 'Unreachable / Dead Code Detected',
                        'explanation': f'Statements after `{type(stmt).__name__.lower()}` on line {stmt.lineno} will never be executed.',
                        'evidence': lines[next_stmt.lineno - 1].strip(),
                        'suggested_fix': 'Remove unreachable dead code to keep code clean and maintainable.',
                        'rule_id': 'DEAD001',
                        'sources': ['ast-analyzer'],
                    })
                    break

    return smells


def analyze_file_metrics(path: str, source: str) -> dict[str, Any]:
    """Computes comprehensive code metrics and quality indicators for a Python source file."""
    lines = source.splitlines()
    loc = len(lines)
    sloc = len([l for l in lines if l.strip() and not l.strip().startswith('#')])
    comment_lines = len([l for l in lines if l.strip().startswith('#')])

    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError) as exc:
        return {
            'path': path,
            'loc': loc,
            'sloc': sloc,
            'comment_lines': comment_lines,
            'syntax_error': str(exc),
            'cyclomatic_complexity': 0,
            'cognitive_complexity': 0,
            'maintainability_index': 0.0,
            'functions': [],
            'smells': [],
            'halstead': {},
        }

    # Module-level Halstead
    halstead = calculate_halstead(tree)

    # Function-level complexity
    functions = []
    total_cyclomatic = 0
    total_cognitive = 0

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            cyc_visitor = CyclomaticComplexityVisitor()
            cyc_visitor.visit(node)
            cog_visitor = CognitiveComplexityVisitor()
            cog_visitor.visit(node)

            cyc = cyc_visitor.complexity
            cog = cog_visitor.complexity
            total_cyclomatic += cyc
            total_cognitive += cog

            functions.append({
                'name': node.name,
                'start_line': node.lineno,
                'end_line': node.end_lineno or node.lineno,
                'cyclomatic_complexity': cyc,
                'cognitive_complexity': cog,
                'risk': 'high' if cyc > 15 else ('medium' if cyc > 8 else 'low'),
            })

    # Module-level cyclomatic complexity
    module_cyc_visitor = CyclomaticComplexityVisitor()
    module_cyc_visitor.visit(tree)
    module_cyclomatic = module_cyc_visitor.complexity

    # Maintainability Index (SEI formula)
    # MI = 171 - 5.2 * ln(Halstead Volume) - 0.23 * Cyclomatic - 16.2 * ln(SLOC)
    vol = max(1.0, halstead['volume'])
    sloc_val = max(1, sloc)
    mi_raw = 171.0 - (5.2 * math.log(vol)) - (0.23 * module_cyclomatic) - (16.2 * math.log(sloc_val))
    maintainability_index = max(0.0, min(100.0, round((mi_raw * 100.0) / 171.0, 1)))

    smells = analyze_code_smells(source, tree, path)

    return {
        'path': path,
        'loc': loc,
        'sloc': sloc,
        'comment_lines': comment_lines,
        'comment_density': round((comment_lines / max(1, loc)) * 100, 1),
        'cyclomatic_complexity': module_cyclomatic,
        'cognitive_complexity': total_cognitive,
        'maintainability_index': maintainability_index,
        'functions': functions,
        'smells': smells,
        'halstead': halstead,
        'syntax_error': None,
    }


def compute_project_score(metrics_list: list[dict[str, Any]], findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Calculates overall project Code Health Score (0-100) and letter grade."""
    score = 100.0

    # Severity penalties
    penalties = {
        'critical': 25.0,
        'high': 15.0,
        'medium': 6.0,
        'low': 2.0,
        'informational': 0.5,
    }

    deductions = {'security': 0.0, 'bugs': 0.0, 'maintainability': 0.0}

    for f in findings:
        sev = f.get('severity', 'medium')
        cat = f.get('category', 'maintainability')
        p = penalties.get(sev, 5.0)
        if cat == 'security':
            deductions['security'] += p
        elif cat == 'bug':
            deductions['bugs'] += p
        else:
            deductions['maintainability'] += p
        score -= p

    # Complexity penalty
    avg_mi = sum(m.get('maintainability_index', 70.0) for m in metrics_list) / max(1, len(metrics_list))
    if avg_mi < 50:
        score -= (50 - avg_mi) * 0.3

    final_score = max(0.0, min(100.0, round(score, 1)))

    if final_score >= 90:
        grade = 'A'
        rating = 'Excellent'
    elif final_score >= 80:
        grade = 'B'
        rating = 'Good'
    elif final_score >= 65:
        grade = 'C'
        rating = 'Fair - Needs Improvement'
    elif final_score >= 50:
        grade = 'D'
        rating = 'Poor - Significant Technical Debt'
    else:
        grade = 'F'
        rating = 'Critical - Multiple Severe Flaws'

    return {
        'health_score': final_score,
        'grade': grade,
        'rating': rating,
        'average_maintainability_index': round(avg_mi, 1),
        'deductions': deductions,
        'total_findings': len(findings),
    }
