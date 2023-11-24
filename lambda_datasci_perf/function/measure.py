import json
from timing import Timer

modules = [ 'numpy', 'pandas', 'pyarrow', 'pyarrow.parquet', 'boto3' ]

def measure_import_time():
    import_times_by_package = {}

    for module in modules:
        timer = Timer()
        with timer:
            __import__(module)
        import_times_by_package[module] = timer.elapsed_us

    return import_times_by_package

if __name__ == "__main__":
    print(json.dumps(measure_import_time(), indent=4))