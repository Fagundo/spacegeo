"""Name-to-class registries so configs can select implementations by name.

Supports the open/closed principle: new scrapers, features or models are
added by registering a class, not by editing a dispatch ``if`` chain.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

from spacegeo.common.exceptions import RegistryError


class Registry[T]:
    """A typed registry mapping names to classes of kind ``T``.

    Example:
        >>> SCRAPERS: Registry[Scraper] = Registry("scraper")
        >>> @SCRAPERS.register("usgs")
        ... class UsgsScraper(Scraper): ...
    """

    def __init__(self, kind: str) -> None:
        self._kind = kind
        self._items: dict[str, type[T]] = {}

    def register(self, name: str) -> Callable[[type[T]], type[T]]:
        """Class decorator that registers ``cls`` under ``name``."""

        def decorator(cls: type[T]) -> type[T]:
            if name in self._items:
                raise RegistryError(f"{self._kind} {name!r} is already registered.")
            self._items[name] = cls
            return cls

        return decorator

    def get(self, name: str) -> type[T]:
        """Return the class registered under ``name``."""
        try:
            return self._items[name]
        except KeyError:
            known = ", ".join(sorted(self._items)) or "none"
            raise RegistryError(f"Unknown {self._kind} {name!r}. Known: {known}.") from None

    def names(self) -> list[str]:
        """Registered names, sorted."""
        return sorted(self._items)

    def __contains__(self, name: object) -> bool:
        return name in self._items

    def __iter__(self) -> Iterator[str]:
        return iter(self.names())

    def __len__(self) -> int:
        return len(self._items)
