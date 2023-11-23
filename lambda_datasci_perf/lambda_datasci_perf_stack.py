from os import path
from aws_cdk import (
    DockerImage,
    Duration,
    Stack,
    aws_lambda as lamb,
    aws_lambda_event_sources as event_sources,
    aws_sqs as sqs,
    aws_ecr_assets as ecr_assets,
    aws_cloudwatch as cloudwatch,
)
from constructs import Construct

TIMEOUT_SECONDS = 660
FUNCTION_MEMORY = 1024

POWERTOOLS_METRICS_NAMESPACE = 'LambdaDatasciPerfStack'

def _service_name_from_function_name(function_name: str) -> str:
    return '_'.join(function_name.split('_')[:-1])

class LambdaDatasciPerfStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        if self.node.try_get_context('slicWatch.enabled'):
            self.add_transform('SlicWatch-v3')
            self.template_options.metadata = {
                'slicWatch': {
                    'enabled': True,
                    'alarms': {
                        'enabled': False
                    }
                }
            }

        runtimes = {
            "Python38": {
                "Runtime": lamb.Runtime.PYTHON_3_8,
                "SDKForPandasLayer": f"arn:aws:lambda:{self.region}:336392948345:layer:AWSSDKPandas-Python38:11",
                "PowertoolsLayer": f"arn:aws:lambda:{self.region}:017000801446:layer:AWSLambdaPowertoolsPythonV2:46",
                "ImageVersion": "3.8"
            },
            "Python39": {
                "Runtime": lamb.Runtime.PYTHON_3_9,
                "SDKForPandasLayer": f"arn:aws:lambda:{self.region}:336392948345:layer:AWSSDKPandas-Python39:11",
                "PowertoolsLayer": f"arn:aws:lambda:{self.region}:017000801446:layer:AWSLambdaPowertoolsPythonV2:46",
                "ImageVersion": "3.9"
            },
            "Python310": {
                "Runtime": lamb.Runtime.PYTHON_3_10,
                "SDKForPandasLayer": f"arn:aws:lambda:{self.region}:336392948345:layer:AWSSDKPandas-Python310:6",
                "PowertoolsLayer": f"arn:aws:lambda:{self.region}:017000801446:layer:AWSLambdaPowertoolsPythonV2:46",
                "ImageVersion": "3.10"
            },
            "Python311": {
                "Runtime": lamb.Runtime.PYTHON_3_11,
                "SDKForPandasLayer": f"arn:aws:lambda:{self.region}:336392948345:layer:AWSSDKPandas-Python311:3",
                "PowertoolsLayer": f"arn:aws:lambda:{self.region}:017000801446:layer:AWSLambdaPowertoolsPythonV2:46",
                "ImageVersion": "3.11"
            },
        }

        common_function_kwargs = dict(
            timeout=Duration.seconds(TIMEOUT_SECONDS),
            retry_attempts=0,
            memory_size=FUNCTION_MEMORY,
            architecture=lamb.Architecture.X86_64,
            tracing=lamb.Tracing.ACTIVE,
        )

        functions_by_name: dict[str, lamb.Function] = {}
        for (runtime_label, runtime_props) in runtimes.items():
            runtime = runtime_props["Runtime"]
            asset_code = lamb.Code.from_asset(
                path.join(path.dirname(__file__), "function"),
                bundling={
                    # We explicitly set the right architecture version of the image because
                    # runtime.bundling_image is not arch-specific and may result in arm64 .so's being deployed
                    # to x86_64 lambda functions
                    "image": DockerImage.from_registry(f"public.ecr.aws/sam/build-{runtime.name}:latest-x86_64"),
                    "platform": ecr_assets.Platform.LINUX_AMD64.platform,
                    "command": [
                        "bash",
                        "-c",
                        "pip install -r requirements-lambda.txt -t /asset-output && " 
                            "find /asset-output -type f -name \"*.so\" -exec strip {} \; && "
                            "find /asset-output -wholename \"*/tests/*\" -type f -delete && "
                            "find /asset-output -regex '^.*\(__pycache__\|\.py[co]\)$' -delete && "
                            "rm -rf /asset-output/boto* && "
                            "rm -rf /asset-output/urllib3* && "
                            "cp -au . /asset-output"
                    ],
                },
            )
            zip_function_name = f"perf_zip_{runtime_label}"
            environment = {
                "POWERTOOLS_METRICS_NAMESPACE": POWERTOOLS_METRICS_NAMESPACE,
                "POWERTOOLS_SERVICE_NAME": _service_name_from_function_name(zip_function_name)
            }
            functions_by_name[zip_function_name] = lamb.Function(
                self,
                zip_function_name,
                **common_function_kwargs,
                environment=environment,
                code=asset_code,
                handler='handler.handle_event',
                runtime=runtime,
                function_name=zip_function_name,
            )
            
            # Create a function to measure module import times on cold starts
            measure_zip_function_name = f'{zip_function_name}_import_measure'
            lamb.Function(
                self,
                measure_zip_function_name,
                **common_function_kwargs,
                environment=environment,
                code=asset_code,
                handler='measurement_handler.handle_event',
                runtime=runtime,
                function_name=measure_zip_function_name
            )

            zip_layers_function_name = f"perf_zip_layers_{runtime_label}"
            functions_by_name[zip_layers_function_name] = lamb.Function(
                self,
                zip_layers_function_name,
                **common_function_kwargs,
                environment={
                    "POWERTOOLS_METRICS_NAMESPACE": POWERTOOLS_METRICS_NAMESPACE,
                    "POWERTOOLS_SERVICE_NAME": _service_name_from_function_name(zip_layers_function_name)
                },
                code=lamb.Code.from_asset(
                    path.join(path.dirname(__file__), 'function'),
                ),
                layers=[
                    lamb.LayerVersion.from_layer_version_arn(
                        self, f'perf_zip_{runtime_label}_powertools_layer',
                        layer_version_arn=runtime_props['PowertoolsLayer']
                    ),
                    lamb.LayerVersion.from_layer_version_arn(
                        self, f'perf_zip_{runtime_label}_sdk_for_pandas_layer',
                        layer_version_arn=runtime_props['SDKForPandasLayer']
                    )
                ],
                handler='handler.handle_event',
                runtime=runtime,
                function_name=zip_layers_function_name,
            )
            
            # Create a function to measure module import times on cold starts
            measure_zip_layers_function_name = f'{zip_layers_function_name}_import_measure'
            lamb.Function(
                self,
                measure_zip_layers_function_name,
                **common_function_kwargs,
                environment=environment,
                code=asset_code,
                handler='measurement_handler.handle_event',
                runtime=runtime,
                function_name=measure_zip_layers_function_name
            )

            image_function_name = f"perf_image_{runtime_label}"
            functions_by_name[image_function_name] = lamb.DockerImageFunction(
                self,
                f'perf_image_{runtime_label}',
                **common_function_kwargs,
                environment={
                    "POWERTOOLS_METRICS_NAMESPACE": POWERTOOLS_METRICS_NAMESPACE,
                    "POWERTOOLS_SERVICE_NAME": _service_name_from_function_name(image_function_name)
                },
                code=lamb.DockerImageCode.from_image_asset(
                    path.dirname(__file__),
                    build_args={'PYTHON_VERSION': runtime_props['ImageVersion']},
                    platform=ecr_assets.Platform.LINUX_AMD64
                ),
                function_name=image_function_name,
            )
            # Create a function to measure module import times on cold starts
            measure_image_function_name = f'{image_function_name}_import_measure'
            lamb.Function(
                self,
                measure_image_function_name,
                **common_function_kwargs,
                environment=environment,
                code=asset_code,
                handler='measurement_handler.handle_event',
                runtime=runtime,
                function_name=measure_image_function_name
            )

        dash = cloudwatch.Dashboard(
            self, "LambdaDatasciPerfDashboard", 
            dashboard_name="LambdaDatasciPerfDashboard",
            default_interval=Duration.hours(1),
            period_override=cloudwatch.PeriodOverride.AUTO
        )

        metric_stats = ("P99", "Maximum", "Average")
        for stat in metric_stats:
            dash.add_widgets(cloudwatch.SingleValueWidget(
                title=f"Lambda Duration {stat}",
                set_period_to_time_range=True,
                width=24,
                height=6,
                metrics=[functions_by_name[function_name].metric_duration(statistic=stat, label=function_name) for function_name in sorted(functions_by_name.keys())]
            ))

        dash.add_widgets(cloudwatch.SingleValueWidget(
            title="Cold Start Counts",
            set_period_to_time_range=True,
            width=24,
            height=6,
            metrics=[
                cloudwatch.Metric(metric_name='ColdStart', namespace=POWERTOOLS_METRICS_NAMESPACE, dimensions_map={
                    'function_name': function_name, 'service': _service_name_from_function_name(function_name)
                }, statistic=cloudwatch.Statistic.SUM.name, label=function_name)
                for function_name in sorted(functions_by_name.keys())
            ]
        ))

        dash.add_widgets(cloudwatch.SingleValueWidget(
            title="Lambda Invocations",
            set_period_to_time_range=True,
            width=24,
            height=6,
            metrics=[functions_by_name[function_name].metric_invocations(statistic=cloudwatch.Statistic.SUM.name, label=function_name) for function_name in sorted(functions_by_name.keys())]
        ))

        dash.add_widgets(cloudwatch.SingleValueWidget(
            title=f"Invocation Counts",
            set_period_to_time_range=True,
            width=24,
            height=6,
            metrics=[
                functions_by_name[function_name].metric_invocations(
                    statistic=cloudwatch.Statistic.SUM.name, label=function_name
                ) for function_name in sorted(functions_by_name.keys())
            ]
        ))

        for stat_label, query in (
            ('p99', 'pct(@initDuration, 99) as p99_init_duration'),
            ('max', 'max(@initDuration) as max_init_duration'),
            ('avg', 'avg(@initDuration) as avg_init_duration'),
            ('min', 'min(@initDuration) as min_init_duration')
        ):
            dash.add_widgets(cloudwatch.LogQueryWidget(
                title=f"Cold Start Durations {stat_label}",
                log_group_names=[f.log_group.log_group_name for f in functions_by_name.values()],
                width=24,
                height=6,
                query_lines=[
                    "filter @type='REPORT'",
                    "parse @log '/aws/lambda/*' as function_name",
                    f"stats {query} by function_name",
                    "sort function_name asc"
                ],
                view=cloudwatch.LogQueryVisualizationType.BAR
            ))

        dash.add_widgets(cloudwatch.SingleValueWidget(
            title="Lambda Concurrent Executions",
            set_period_to_time_range=True,
            width=24,
            height=6,
            metrics=[functions_by_name[function_name].metric(
                statistic=cloudwatch.Statistic.MAXIMUM.name, label=function_name, metric_name='ConcurrentExecutions'
            ) for function_name in sorted(functions_by_name.keys())]
        ))
