from argparse import HelpFormatter, Action
from typing import Sequence


class SortingHelpFormatter(HelpFormatter):
    """
    A help formatter for argparse that sorts arguments alphabetically by their first option string,
    within each argument group (e.g., optional args, positional args).
    """

    def add_arguments(self, actions: Sequence[Action]) -> None:
        def sort_key(a: Action) -> str:
            if a.option_strings:
                return a.option_strings[0]
            return a.dest  # for positional args

        actions = sorted(actions, key=sort_key)
        super().add_arguments(actions)
