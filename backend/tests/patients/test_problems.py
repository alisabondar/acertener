from app.patients.problems import is_chronic, order_problems


def test_chronic_conditions_are_recognized_by_icd10_category() -> None:
    assert is_chronic("E11.9")  # type 2 diabetes
    assert is_chronic("I10")  # hypertension
    assert is_chronic("J45.909")  # asthma
    assert not is_chronic("R05.1")  # acute cough
    assert not is_chronic("M54.50")  # low back pain


def test_todays_reason_comes_first_then_chronic_conditions_then_the_rest() -> None:
    conditions = [
        ("R05.1", "Acute cough"),
        ("I10", "Essential hypertension"),
        ("M54.50", "Low back pain"),
        ("E11.9", "Type 2 diabetes"),
    ]

    assert order_problems("Medication review", conditions) == [
        "Today: Medication review",
        "Essential hypertension",
        "Type 2 diabetes",
        "Acute cough",
        "Low back pain",
    ]


def test_without_a_visit_today_the_list_starts_with_chronic_conditions() -> None:
    assert order_problems(None, [("R05.1", "Acute cough"), ("E78.5", "Hyperlipidemia")]) == [
        "Hyperlipidemia",
        "Acute cough",
    ]
