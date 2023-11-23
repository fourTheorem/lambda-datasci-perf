import subprocess
import json
from pathlib import Path

def measure_import_time(handler_file):
    """"
    Run `python -X importtime` with the Lambda Handler to measure and log the module reporting times in us
    Example output we want to parse

    import time: self [us] | cumulative | imported package
    import time:       161 |        161 |   _io
    import time:        30 |         30 |   marshal
    import time:       287 |        287 |   posix
    import time:       726 |       1204 | _frozen_importlib_external
    import time:       740 |        740 |   time
    import time:       205 |        944 | zipimport
    import time:       147 |        147 |     _codecs
    import time:       518 |        665 |   codecs
    import time:       559 |        559 |   encodings.aliases
    import time:       845 |       2068 | encodings
    import time:       231 |        231 | encodings.utf_8
    import time:        85 |         85 | _signal
    import time:        35 |         35 |     _abc
    import time:       278 |        313 |   abc
    import time:       284 |        597 | io
    """

    result = subprocess.run(["python", "-X", "importtime", handler_file], capture_output=True, text=True)

    import_times_by_package = {}
    for line in result.stderr.splitlines()[1:]:
        parts = line.split('|')
        cumulative_time = parts[-2].strip()
        imported_package = parts[-1][1:] # strip the leading, padding space
        if not imported_package.startswith(' '): # Skip nested submodules
            package_name = imported_package.strip()
            import_times_by_package[package_name] = cumulative_time

    return import_times_by_package

if __name__ == "__main__":
    handler_file = str((Path(__file__).parent / "handler.py").resolve())
    print(json.dumps(measure_import_time(handler_file), indent=4))