import os
import sys

# The windowed executable has no console, so print() would fail; send the output nowhere instead.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

if len(sys.argv) > 1:
    # Arguments mean the command line: python -m repo_xray <project> --export docs.zip
    from repo_xray.cli import main
else:
    # No arguments, e.g. a double-click on the executable: open the window.
    from repo_xray.app.main import run as main

sys.exit(main())
