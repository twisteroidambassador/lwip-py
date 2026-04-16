import enum

@enum.global_enum
class ErrorCode(enum.IntEnum):
    ERR_OK = 0
    ERR_MEM = -1
    ERR_BUF = -2
    ERR_TIMEOUT = -3
    ERR_RTE = -4
    ERR_INPROGRESS = -5
    ERR_VAL = -6
    ERR_WOULDBLOCK = -7
    ERR_USE = -8
    ERR_ALREADY = -9
    ERR_ISCONN = -10
    ERR_CONN = -11
    ERR_IF = -12
    ERR_ABRT = -13
    ERR_RST = -14
    ERR_CLSD = -15
    ERR_ARG = -16