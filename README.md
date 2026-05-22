# lwip-py

A Python binding for lwIP on Linux.

## Features:

- lwIP compile options optimized for full Linux hosts
- Running one or more (to emulate several distinct hosts) user-space TCP/IP network stack(s)
  - Layer 3 interface only at the moment
  - IPv4 and IPv6 support
- APIs compatible with Python standard library:
  - TCP and UDP sockets like `socket.socket`
  - Poll objects like `select.poll`
  - Selector like those in `selectors` module
  - TODO: `asyncio` event loop

## How to build
 - Clone repo with submodules
 - Build liblwip with CMake (`mkdir liblwip/build && cd liblwip/build && cmake .. && make -j$(nproc)`)
 - Copy generated file `liblwip/build/headers.py` to `src/lwip/headers.py`
 - Make pip package (`python -m build`)
 - Install pip package (`python -m pip install ./dist/lwip_py-[...].whl`)
 - Copy `liblwip.so` to some path
 - Add an environment variable `LIBLWIP_PATH` with the absolute path to `liblwip.so`
 - Run tests to ensure everything is working properly (Ex: `python tests/tests_tcp.py`)
