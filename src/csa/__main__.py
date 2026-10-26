"""Allow `python -m csa ...` as an alternative to the `csa` console script."""

from csa.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
