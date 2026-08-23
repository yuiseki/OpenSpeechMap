"""`python -m openspeechmap.cli_main` for the tests.

The installed console script is `speechmap`. Tests invoke the same app through
this module so they exercise the package as imported rather than whatever
happens to be on PATH.
"""
from __future__ import annotations

from openspeechmap.cli import speechmap


def main() -> None:
    speechmap()


if __name__ == "__main__":
    main()
