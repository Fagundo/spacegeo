"""Exception hierarchy shared across spacegeo."""


class SpacegeoError(Exception):
    """Base class for all spacegeo errors."""


class TimeZoneError(SpacegeoError):
    """A timestamp or index is naive or not in UTC."""


class SchemaError(SpacegeoError):
    """A DataFrame does not match its declared schema."""


class ConfigError(SpacegeoError):
    """A configuration file or value is invalid."""


class RegistryError(SpacegeoError):
    """A registry lookup or registration failed."""


class NotFittedError(SpacegeoError):
    """A stateful component was used before being fitted."""


class LeakageError(SpacegeoError):
    """An operation would use data from at or after the forecast time."""
