import contextlib
import os

from .ffi import ffi
from .defs import ErrorCode

class LwipError(Exception):
    pass


def check_ret(func: str, ret: int) -> int:
    """
    Check whether ret is equal to ERR_OK. If not, raise LwipError.

    Use this for non-socket LwIP functions that returns an error code ERR_*.

    :param func: the name of the function whose return value is being checked.
    :param ret: the return value.

    :returns: the original return value.
    """
    if ret != ErrorCode.ERR_OK:
        with contextlib.suppress(KeyError):
            ret = ErrorCode(ret)
        raise LwipError(f'{func} failed with return value {ret!r}')
    return ret


def check_ret_errno(
        function_name: str,
        function,
        *args,
        **kwargs
):
    """
    Check whether the return value of errno indicates error. If so, raise LwipError or OSError.

    Use this for socket LwIP functions that return <0 and set errno for errors.

    This method clears errno before invoking function(*args, **kwargs).

    :param function_name: the name of the function.
    :param function: the function itself.
    :param args: positional arguments.
    :param kwargs: named arguments.

    :returns: the original return value.
    """
    ffi.errno = 0
    ret = function(*args, **kwargs)
    if (errno := ffi.errno):
        raise OSError(errno, f'LwIP {function_name} returned {ret}, errno {errno}: {os.strerror(errno)}')
    if ret < 0:
        raise LwipError(f'{function_name} returnd {ret}')
    return ret
