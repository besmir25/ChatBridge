"""Start a new version:  python bump_version.py 1.1.0

Sets the version in the app, and turns the 'Unreleased' notes in CHANGELOG.md into this version's section.
Then follow RELEASING.md: commit, tag (v1.1.0), push - GitHub builds and publishes the release.
"""
import os
import sys

import release_tools

if len(sys.argv) != 2:
    sys.exit(__doc__)
try:
    for line in release_tools.bump(sys.argv[1], os.path.dirname(os.path.abspath(__file__))):
        print(" -", line)
except ValueError as e:
    sys.exit(str(e))
v = sys.argv[1]
print(f"\nNext: edit CHANGELOG.md if needed, then\n  git commit -am \"Release {v}\"\n  git tag v{v}\n  git push origin main v{v}")
