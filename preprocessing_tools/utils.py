from pathlib import Path


def ensure_dir(dirname: Path) -> None:
    """
    Create directory only if it does not exist yet.
    Throw an error otherwise.
    """
    dirname = Path(dirname)
    if not dirname.is_dir():
        dirname.mkdir(parents=True, exist_ok=False)


def flatten(t):
    return [item for sublist in t for item in sublist]
