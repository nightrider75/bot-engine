#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

from typing import Any, Dict

# Track which modules we've already warned about
_warned_modules = set()


def _warn_deprecated_access(globals: Dict[str, Any], attr, old: str, new: str):
    # Only warn once per old->new module pair
    module_key = (old, new)
    if module_key not in _warned_modules:
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("always")
            warnings.warn(
                f"Module `bot_engine.services.{old}` is deprecated, use `bot_engine.services.{new}` instead.",
                DeprecationWarning,
                stacklevel=3,
            )
        _warned_modules.add(module_key)

    return globals[attr]


class DeprecatedModuleProxy:
    """A proxy class that intercepts attribute access to deprecated modules and issues warnings.

    This class acts as a transparent proxy for deprecated modules, allowing existing code
    to continue working while warning users about the deprecation. When attributes are
    accessed on the proxy, it checks if they exist in the original module's globals
    and issues a deprecation warning before returning the requested attribute.

    Args:
        globals (Dict[str, Any]): The global namespace of the deprecated module containing
            all its attributes and functions.
        old (str): The name of the deprecated module being proxied.
        new (str): The name of the recommended replacement module.

    Raises:
        AttributeError: When attempting to access an attribute that doesn't exist in the
            deprecated module's globals.

    Example:
        >>> # Create a proxy for a deprecated 'old_service' module
        >>> proxy = DeprecatedModuleProxy(
        ...     globals=old_service_globals,
        ...     old='old_service',
        ...     new='new_service'
        ... )
        >>> # Accessing attributes will trigger deprecation warnings
        >>> result = proxy.some_function()  # Issues warning and returns function
    """

    def __init__(self, globals: Dict[str, Any], old: str, new: str):
        """Initialize a string replacement configuration.

        Args:
            globals (Dict[str, Any]): Dictionary containing global configuration settings
                and context information.
            old (str): The original string value to be replaced.
            new (str): The new string value to replace the old value with.
        """
        self._globals = globals
        self._old = old
        self._new = new

    def __getattr__(self, attr):
        if attr in self._globals:
            return _warn_deprecated_access(self._globals, attr, self._old, self._new)
        raise AttributeError(
            f"module 'bot_engine.services.{self._old}' has no attribute '{attr}'"
        )
