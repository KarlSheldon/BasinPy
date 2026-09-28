# BetaBasic.py
# This file was previously an exact 55,000-line duplicate of main.py.
# To improve maintainability and prevent bugs having to be fixed twice, 
# this has been replaced with a stub that imports and runs main.py.

import sys
import os

if __name__ == "__main__":
    # Ensure the script directory is in the path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
        
    # main.py does a lot of initialization at module level when __name__ == '__main__'
    # We can execute it directly to replicate exact duplicate behavior.
    main_path = os.path.join(script_dir, "main.py")
    with open(main_path, "r", encoding="utf-8") as f:
        code = f.read()
        
    exec(code, {"__name__": "__main__", "__file__": main_path})
