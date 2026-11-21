import pytest
from app.metrics import (
    analyze_file_metrics,
    CyclomaticComplexityVisitor,
    CognitiveComplexityVisitor,
    compute_project_score,
)
import ast


def test_cyclomatic_complexity_basic():
    code = """
def check_val(x):
    if x > 10:
        return True
    elif x < 0:
        return False
    return None
"""
    tree = ast.parse(code)
    func_node = tree.body[0]
    visitor = CyclomaticComplexityVisitor()
    visitor.visit(func_node)
    # 1 base + 1 (if) + 1 (elif) = 3
    assert visitor.complexity == 3


def test_cognitive_complexity_nesting():
    code = """
def nested_func(items):
    for a in items:
        if a > 0:
            while a < 10:
                a += 1
"""
    tree = ast.parse(code)
    func_node = tree.body[0]
    visitor = CognitiveComplexityVisitor()
    visitor.visit(func_node)
    # for (+1), if inside for (+1 + 1 nesting), while inside if (+1 + 2 nesting) = 1 + 2 + 3 = 6
    assert visitor.complexity >= 5


def test_analyze_file_metrics_complete():
    code = """
# Module docstring comment
def process_data(items, flag=True):
    results = []
    for item in items:
        if item > 0:
            results.append(item * 2)
    return results
"""
    metrics = analyze_file_metrics("test_module.py", code)
    assert metrics["path"] == "test_module.py"
    assert metrics["loc"] == len(code.splitlines())
    assert metrics["sloc"] >= 5
    assert metrics["cyclomatic_complexity"] >= 2
    assert "maintainability_index" in metrics
    assert metrics["maintainability_index"] > 0
    assert len(metrics["functions"]) == 1
    assert metrics["functions"][0]["name"] == "process_data"


def test_smell_detection_secrets_and_bare_except():
    code = """
def insecure():
    api_key = "1234567890abcdef1234567890abcdef"
    try:
        do_work()
    except:
        pass
    return True
    print("Dead code")
"""
    metrics = analyze_file_metrics("insecure.py", code)
    smells = metrics["smells"]
    rule_ids = {s["rule_id"] for s in smells}
    assert "SEC001" in rule_ids
    assert "ERR001" in rule_ids
    assert "DEAD001" in rule_ids


def test_project_health_score():
    metrics = [
        {"maintainability_index": 85.0, "loc": 50},
        {"maintainability_index": 90.0, "loc": 40},
    ]
    findings = [
        {"severity": "critical", "category": "security"},
        {"severity": "low", "category": "maintainability"},
    ]
    score = compute_project_score(metrics, findings)
    assert score["health_score"] < 100
    assert score["grade"] in ("A", "B", "C", "D", "F")
    assert "rating" in score
