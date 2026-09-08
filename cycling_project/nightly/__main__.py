"""``python -m cycling_project.nightly <command>`` → the nightly driver."""

import os
import sys

# stdout carries exactly one JSON document per command; every log line goes to stderr.
os.environ.setdefault("CYCLING_LOG_STREAM", "stderr")

from cycling_project.nightly.driver import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
