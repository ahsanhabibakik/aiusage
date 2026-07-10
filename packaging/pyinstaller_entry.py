"""PyInstaller entry point.

A file inside the package (src/aiusage/__main__.py) can't be handed to
PyInstaller directly -- running it as a top-level script breaks the
package's relative imports ("attempted relative import with no known
parent package"). This top-level shim imports the package properly.
"""
from aiusage.cli import main

if __name__ == "__main__":
    main()
