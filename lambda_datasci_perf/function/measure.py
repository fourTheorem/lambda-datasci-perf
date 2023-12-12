from timed_import import ImportTimer
import_timer = ImportTimer()

np = import_timer.import_module('numpy')
pd = import_timer.import_module('pandas')
pa = import_timer.import_module('pyarrow')
pq = import_timer.import_module('pyarrow.parquet').parquet
boto3 = import_timer.import_module('boto3')
powertools = import_timer.import_module('aws_lambda_powertools')
json = import_timer.import_module('json')

def measure_import_time():
    pd.DataFrame()
    np.array([])
    boto3.session.Session()
    powertools.Logger()
    json.loads('{}')
    print(pa.Table)
    print(pq.write_table)
    return import_timer.timings

if __name__ == "__main__":
    print(json.dumps(measure_import_time(), indent=4))