class ProviderError(Exception):
    """Base error raised while communicating with an official provider."""


class ProviderTimeoutError(ProviderError):
    """The official provider did not respond before the configured timeout."""


class ProviderUnavailableError(ProviderError):
    """The official provider is temporarily unavailable."""


class UnexpectedProviderResponseError(ProviderError):
    """The official response did not match its verified schema."""


class ProviderDataNotFoundError(ProviderError):
    """Required team data was not present in an otherwise valid response."""
