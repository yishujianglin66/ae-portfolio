import sys
print(f"Python {sys.version}")

import DaVinciResolveScript as bmd
print("Import OK")

resolve = bmd.scriptapp("Resolve")
print(f"Resolve: {resolve}")
if resolve:
    print(f"Version: {resolve.GetVersionString()}")
