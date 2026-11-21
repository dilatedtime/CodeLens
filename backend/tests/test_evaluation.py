import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location('evaluation',Path(__file__).parents[2]/'evaluation'/'evaluate.py')
evaluation=importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


def test_one_to_one_matching_counts_duplicate_as_false_positive():
    finding={'path':'main.py','start_line':2,'end_line':3,'category':'bug'}
    assert evaluation.score([finding,finding],[finding]) == {'tp':1,'fp':1,'fn':0}


def test_mismatched_category_is_not_automatically_correct():
    label={'path':'main.py','start_line':2,'end_line':2,'category':'security'}
    assert evaluation.score([{**label,'category':'style'}],[label]) == {'tp':0,'fp':1,'fn':1}
