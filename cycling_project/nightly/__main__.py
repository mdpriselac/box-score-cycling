"""``python -m cycling_project.nightly <command>`` → the nightly driver."""

import sys

from cycling_project.nightly.driver import main

if __name__ == "__main__":
    sys.exit(main())
