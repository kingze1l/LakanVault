# entry point for the daemon / tray launcher
"""LakanVault daemon entry point."""
import multiprocessing
import sys

from lakanvault.launcher.bootstrap import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
