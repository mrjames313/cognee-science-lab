"""Host-only launcher: skip native extension teardown after CLI explicit close."""
import subprocess
import sys

_original_run = subprocess.run
_LAUNCH = '''import os, runpy, sys
sys.argv = ["cognee_lab.identity", *sys.argv[1:]]
try:
    runpy.run_module("cognee_lab.identity", run_name="__main__")
except SystemExit as exc:
    code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
except BaseException:
    import traceback
    traceback.print_exc()
    code = 1
else:
    code = 0
sys.stdout.flush()
sys.stderr.flush()
os._exit(code)
'''

def run(args, *positional, **kwargs):
    if isinstance(args, list) and args[1:3] == ['-m', 'cognee_lab.identity']:
        args = [args[0], '-c', _LAUNCH, *args[3:]]
    return _original_run(args, *positional, **kwargs)

subprocess.run = run
import pytest
raise SystemExit(pytest.main(sys.argv[1:]))
