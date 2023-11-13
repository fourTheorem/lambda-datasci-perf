import base64
import sys
from datetime import datetime, timedelta
from random import randint
from time import sleep
import json
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from aws_lambda_powertools import Logger, Tracer, Metrics

# Initialize Logger and Tracer from aws_lambda_powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics()

np.random.seed(0)

@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handle_event(event, context):
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

    # Create the Parquet data
    table = pa.Table.from_pandas(df)
    buf = pa.BufferOutputStream()
    pq.write_table(table, buf)
    parquet_data = buf.getvalue().to_pybytes()

    logger.info(f"DataFrame:\n{df}")
    logger.info(f"Parquet data: {str(parquet_data)}")

    sleep_time = randint(180, 600) 
    logger.info('Sleeping', extra={'sleep_time': sleep_time})
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

