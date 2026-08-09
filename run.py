import sys
import os

if "--mcp" in sys.argv:
    from project.mcp_server import mcp
    mcp.run()
    sys.exit(0)

if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')

from project.app import main

if __name__ == "__main__":
    main()
