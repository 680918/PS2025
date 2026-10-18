"""One local process owns an application's data directory at a time."""

import os
from contextlib import contextmanager


class DataDirectoryBusy(RuntimeError):
    pass


class RestoreIncomplete(RuntimeError):
    pass


@contextmanager
def data_directory_lock(directory):
    path = directory / ".coach.lock"
    if path.is_symlink():
        raise OSError("Invalid lock path")
    with path.open("a+b") as handle:
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise DataDirectoryBusy from error
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
