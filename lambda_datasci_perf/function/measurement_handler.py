import sys
from pathlib import Path
from measure import measure_import_time
from aws_lambda_powertools import Logger, Tracer, Metrics

# Initialize Logger and Tracer from aws_lambda_powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics()

@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics(capture_cold_start_metric=True)
def handle_event(_event, _context):
    logger.info("Python version", extra={"version": sys.version})
    handler_file = str((Path(__file__).parent / "handler.py").resolve())
    measurements = measure_import_time(handler_file)
    logger.info("measurements", extra={"measurements": measurements})
    return measurements
    