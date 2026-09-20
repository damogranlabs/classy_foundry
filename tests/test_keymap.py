"""The table is the single source for dispatch *and* the help window, so the thing worth
testing is that it stays coherent."""

from classy_foundry.view.keymap import BINDINGS, Binding


def test_every_binding_is_fully_described():
    for binding in BINDINGS:
        assert isinstance(binding, Binding)
        assert binding.key and binding.label and binding.description and binding.action


def test_no_key_is_bound_twice():
    keys = [binding.key for binding in BINDINGS]

    assert len(keys) == len(set(keys))


def test_delete_is_not_bound_to_x_which_is_the_x_axis_constraint():
    delete = [binding for binding in BINDINGS if binding.action == "delete"]

    assert len(delete) == 1
    assert delete[0].key.lower() != "x"


def test_the_expected_operations_are_all_present():
    actions = {binding.action for binding in BINDINGS}

    assert actions == {"place_point", "move", "make_block", "delete", "save"}
