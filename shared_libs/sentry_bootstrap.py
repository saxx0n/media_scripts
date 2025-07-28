import sys
import os
import platform
from pathlib import Path
from typing import Callable, Optional
import toml

try:
    import sentry_sdk as _sentry_sdk
except ImportError:
    _sentry_sdk = None

sentry_sdk = _sentry_sdk  # expose for tests


def _default_config_path() -> Path:
    """
    Returns the default config path based on platform.

    Returns:
        Path object to the appropriate config file.
    """
    if platform.system() == "Windows":
        base = os.getenv("PROGRAMDATA", r"C:\ProgramData")
        return Path(base) / "sentry" / "scripts.toml"
    return Path("/etc/sentry.d/scripts.toml")


def init(
    script_override: Optional[str] = None,
    config_path: Optional[str | Path] = None,
    debug_hook: Optional[Callable[[str], None]] = None,
    **kwargs
) -> None:
    """
    Initializes Sentry logging if a DSN is found for this script in config or environment.

    Args:
        script_override: Manually specify the script name (default: stem of sys.argv[0]).
        config_path: Optional path to a TOML config file containing DSNs.
        debug_hook: Optional callable to log debug info (e.g. `debugger.log`).
        **kwargs: Additional sentry_sdk.init() arguments (e.g., traces_sample_rate)
    """
    if sentry_sdk is None:
        if debug_hook:
            debug_hook("[Sentry] sentry_sdk not available")
        return

    script_name = script_override or Path(sys.argv[0]).stem
    config_file = Path(config_path) if config_path else _default_config_path()
    config = {}

    if config_file.exists():
        try:
            config = toml.load(config_file)
        except Exception as e:
            if debug_hook:
                debug_hook(f"[Sentry] Error loading DSN config: {e}")

    dsn = config.get("script_dsns", {}).get(script_name) or os.getenv("SENTRY_DSN")
    if dsn:
        sentry_sdk.init(
            dsn=dsn,
            send_default_pii=True,
            max_request_body_size="always",
            **kwargs,
        )
    elif debug_hook:
        debug_hook(f"[Sentry] No DSN found for script: {script_name}")


# Alias for test compatibility
init_sentry = init
