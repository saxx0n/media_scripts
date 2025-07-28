from sys import stdout
from typing import TextIO


class Debugger:
    """
    A minimal debug logger with tiered verbosity support.
    Outputs to the specified stream (default: stdout).
    """

    def __init__(self, enabled: bool = False, level: int = 1, output: TextIO = stdout):
        """
        Args:
            enabled: Whether debugging is initially enabled.
            level: Debug verbosity level (1 = basic, 2+ = detailed).
            output: Output stream to write to (default: sys.stdout).
        """
        self.enabled = enabled
        self.level = level
        self.out = output

    def set_level(self, level: int) -> None:
        """
        Enables debugging and sets the verbosity level.

        Args:
            level: Verbosity level (1–3).
        """
        self.enabled = True
        self.level = level

    def log(self, msg: str = '', msg_level: int = 1) -> None:
        """
        Emits a debug message if within verbosity threshold.

        Args:
            msg: The message to log.
            msg_level: The severity or depth of the message.
        """
        if not self.enabled or msg_level > self.level:
            return

        if msg != '':
            if self.level > 1:
                self.out.write(f"DEBUG[{msg_level}]: {msg}")
            else:
                self.out.write(f"DEBUG: {msg}")
        self.out.write('\n')
