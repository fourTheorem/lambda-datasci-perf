import sys
from measure import measure_import_time
from aws_lambda_powertools import Logger, Metrics

logger = Logger()
metrics = Metrics()

@logger.inject_lambda_context
@metrics.log_metrics(capture_cold_start_metric=False)
def handle_event(_event, _context):
    logger.info("Python version", extra={"version": sys.version})
    measurements = measure_import_time()
    for module, elapsed_us in measurements.items():
        metrics.add_metric(name=module, unit="Microseconds", value=elapsed_us)
    logger.info("measurements", extra={"measurements": measurements})
    return measurements
    