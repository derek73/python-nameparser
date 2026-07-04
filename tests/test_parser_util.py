from nameparser.parser import group_contiguous_integers


def test_empty_list_returns_no_ranges() -> None:
    assert group_contiguous_integers([]) == []


def test_all_isolated_values_returns_no_ranges() -> None:
    # no two values are adjacent, so nothing counts as a "run"
    assert group_contiguous_integers([1, 3, 5]) == []


def test_single_value_returns_no_ranges() -> None:
    # a run of length 1 isn't a contiguous "run" by this function's definition
    assert group_contiguous_integers([5]) == []


def test_pair_of_adjacent_values_is_smallest_valid_run() -> None:
    assert group_contiguous_integers([4, 5]) == [(4, 5)]


def test_single_contiguous_run() -> None:
    assert group_contiguous_integers([1, 2, 3]) == [(1, 3)]


def test_multiple_separate_contiguous_runs() -> None:
    assert group_contiguous_integers([1, 2, 5, 6, 7, 9]) == [(1, 2), (5, 7)]


def test_isolated_values_between_runs_are_excluded() -> None:
    assert group_contiguous_integers([1, 2, 4, 6, 7]) == [(1, 2), (6, 7)]


def test_unsorted_input_is_not_treated_as_contiguous() -> None:
    # the grouping key (enumerate index - value) only repeats for ascending,
    # strictly increasing runs (as produced by an `enumerate`-based index
    # scan, which is how join_on_conjunctions uses it); a descending
    # sequence changes the key at every step, so no run is ever found
    assert group_contiguous_integers([3, 2, 1]) == []
