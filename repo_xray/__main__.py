import sys

if len(sys.argv) > 1:
    # Arguments mean the command line: python -m repo_xray <project> --export docs.zip
    from repo_xray.cli import main
else:
    # No arguments, e.g. a double-click on the executable: open the window.
    from repo_xray.app.main import run as main

sys.exit(main())
