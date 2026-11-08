class ResourceNotFoundError(Exception):
    pass


class SlugConflictError(Exception):
    pass


class UnsafeDeleteError(Exception):
    pass


class InvalidStateError(Exception):
    pass


class InvalidIdentifierError(Exception):
    pass
