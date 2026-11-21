from pydantic import ValidationError


def format_errors(error: ValidationError, root: str = 'row') -> str:
    """Turn Pydantic's error list into one readable line, e.g. 'title: Field required; url: ...'.

    An error about the whole value (not one field) has no field name; it's shown as 'root'.
    """
    return '; '.join(
        f'{".".join(str(part) for part in e["loc"]) or root}: {e["msg"]}' for e in error.errors()
    )
