"""Frozen entry point, including an isolated distribution smoke test."""
import sys

if __name__ == '__main__':
    if '--smoke-test' in sys.argv:
        from pixel_nonograms.distribution_check import main
    else:
        from pixel_nonograms.app import main
    raise SystemExit(main())
