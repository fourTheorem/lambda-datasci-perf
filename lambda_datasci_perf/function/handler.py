from timed_import import ImportTimer
from timing import Timer

import_timer = ImportTimer()

base64 = import_timer.import_module('base64')
os = import_timer.import_module('os')
sys = import_timer.import_module('sys')

dt = import_timer.import_module('datetime')
datetime = dt.datetime
timedelta = dt.timedelta

json = import_timer.import_module('json')
boto3 = import_timer.import_module('boto3')
np = import_timer.import_module('numpy')
pd = import_timer.import_module('pandas')
pa = import_timer.import_module('pyarrow')
pq = import_timer.import_module('pyarrow.parquet').parquet
powertools = import_timer.import_module('aws_lambda_powertools')

powertools_timer = Timer()
with powertools_timer:
    logger = powertools.Logger()
    tracer = powertools.Tracer()
    metrics = powertools.Metrics()
powertools_init_time = powertools_timer.elapsed_us

boto3_timer = Timer()
with boto3_timer:
    session = boto3.session.Session()
    s3_client = session.client('s3')
boto3_init_time = boto3_timer.elapsed_us

cold_start = powertools.metrics.provider.cold_start

BUCKET_NAME = os.environ['BUCKET_NAME']

@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handle_event(_event, _context):
    if (cold_start):
        all_timings = {
            **import_timer.timings,
            "powertools_init_time": powertools_init_time,
            "boto3_init_time": boto3_init_time
        }
        logger.info("module_timings", extra={"timings": all_timings})
        for mod, elapsed_us in all_timings.items():
            module_identifier = mod.replace('.', '_')
            metrics.add_metric(name=f"module_load_{module_identifier}", unit="Microseconds", value=elapsed_us)

    logger.info('Python version', extra={"version": sys.version})
    # Generate some random data
    order_ids = range(1, 1001)
    product_categories = ['Electronics', 'Clothing', 'Home & Kitchen', 'Sports', 'Toys']
    category = np.random.choice(product_categories, 1000)
    quantities = np.random.randint(1, 11, size=1000)
    unit_prices = np.random.uniform(10, 1000, size=1000).round(2)

    # Generate random purchase dates within the last year
    base_date = datetime.today()
    purchase_dates = [base_date - timedelta(days=np.random.randint(0, 365)) for _ in range(1000)]

    # Create the DataFrame
    df = pd.DataFrame({
        'Order ID': order_ids,
        'Product Category': category,
        'Quantity Sold': quantities,
        'Unit Price': unit_prices,
        'Purchase Date': purchase_dates
    })

    # Format the 'Purchase Date' column to a more readable format
    df['Purchase Date'] = pd.to_datetime(df['Purchase Date']).dt.strftime('%Y-%m-%d')

    # Create parquet data
    table = pa.Table.from_pandas(df)
    buf = pa.BufferOutputStream()
    pq.write_table(table, buf)
    parquet_data = buf.getvalue().to_pybytes()

    logger.info("DataFrame", extra={"df_head": df.head()})

    key = f"{_context.function_name}/{_context.aws_request_id}.parquet"
    s3_client.put_object(Bucket=BUCKET_NAME, Key=key, Body=parquet_data)

    result = {
        'statusCode': 200,
        'body': json.dumps({
            'parquet_data_base64': base64.b64encode(parquet_data).decode('utf-8')
        }),
        'headers': {
            'Content-Type': 'application/json',
        },
    }

    return result

