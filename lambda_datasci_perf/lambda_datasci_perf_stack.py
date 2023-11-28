from os import path
from aws_cdk import (
    DockerImage,
    Duration,
    Stack,
    aws_iam as iam,
    aws_lambda as lamb,
    aws_s3 as s3,
    aws_ecr_assets as ecr_assets,
    aws_cloudwatch as cloudwatch,
)
from constructs import Construct

TIMEOUT_SECONDS = 660
DEFAULT_FUNCTION_MEMORY = 1024

MEMORY_CONFIGS = (1024, 1769, 3538, 10240)

POWERTOOLS_METRICS_NAMESPACE = "LambdaDatasciPerfStack"

class LambdaDatasciPerfStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        if self.node.try_get_context("slicWatch.enabled"):
            self.add_transform("SlicWatch-v3")
            self.template_options.metadata = {
                "slicWatch": {
                    "enabled": True,
                    "alarms": {
                        "enabled": False
                    }
                }
            }

        self.bucket = s3.Bucket(self, "bucket")

        self.runtimes = {
            # "Python38": {
            #     "Runtime": lamb.Runtime.PYTHON_3_8,
            #     "SDKForPandasLayer": f"arn:aws:lambda:{self.region}:336392948345:layer:AWSSDKPandas-Python38:11",
            #     "PowertoolsLayer": f"arn:aws:lambda:{self.region}:017000801446:layer:AWSLambdaPowertoolsPythonV2:46",
            #     "ImageVersion": "3.8"
            # },
            "Python39": {
                "Runtime": lamb.Runtime.PYTHON_3_9,
                "SDKForPandasLayer": f"arn:aws:lambda:{self.region}:336392948345:layer:AWSSDKPandas-Python39:11",
                "PowertoolsLayer": f"arn:aws:lambda:{self.region}:017000801446:layer:AWSLambdaPowertoolsPythonV2:46",
                "ImageVersion": "3.9"
            },
            # "Python310": {
            #     "Runtime": lamb.Runtime.PYTHON_3_10,
            #     "SDKForPandasLayer": f"arn:aws:lambda:{self.region}:336392948345:layer:AWSSDKPandas-Python310:6",
            #     "PowertoolsLayer": f"arn:aws:lambda:{self.region}:017000801446:layer:AWSLambdaPowertoolsPythonV2:46",
            #     "ImageVersion": "3.10"
            # },
            # "Python311": {
            #     "Runtime": lamb.Runtime.PYTHON_3_11,
            #     "SDKForPandasLayer": f"arn:aws:lambda:{self.region}:336392948345:layer:AWSSDKPandas-Python311:3",
            #     "PowertoolsLayer": f"arn:aws:lambda:{self.region}:017000801446:layer:AWSLambdaPowertoolsPythonV2:46",
            #     "ImageVersion": "3.11"
            # },
        }

        functions_by_name = self.create_lambda_functions()

        self.create_dashboard(functions_by_name)

    def create_lambda_functions(self):
        common_envs = { 
            "BUCKET_NAME": self.bucket.bucket_name,
            "POWERTOOLS_METRICS_NAMESPACE": POWERTOOLS_METRICS_NAMESPACE
        }

        common_function_kwargs = dict(
            timeout=Duration.seconds(TIMEOUT_SECONDS),
            retry_attempts=0,
            memory_size=DEFAULT_FUNCTION_MEMORY,
            architecture=lamb.Architecture.X86_64,
            tracing=lamb.Tracing.ACTIVE,
        )

        functions_by_name: dict[str, lamb.Function] = {}
        for (runtime_label, runtime_props) in self.runtimes.items():
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
            for memory_config in MEMORY_CONFIGS:
                zip_function_name = f"perf_zip_{runtime_label}_{memory_config}"
                functions_by_name[zip_function_name] = lamb.Function(
                    self,
                    zip_function_name,
                    **common_function_kwargs,
                    environment={**common_envs, "POWERTOOLS_SERVICE_NAME": zip_function_name},
                    code=asset_code,
                    handler="handler.handle_event",
                    runtime=runtime,
                    function_name=zip_function_name,
                )

            powertools_layer = lamb.LayerVersion.from_layer_version_arn(
                self, f"perf_zip_{runtime_label}_powertools_layer",
                layer_version_arn=runtime_props["PowertoolsLayer"]
            )
            sdk_for_pandas_layer = lamb.LayerVersion.from_layer_version_arn(
                self, f"perf_zip_{runtime_label}_sdk_for_pandas_layer",
                layer_version_arn=runtime_props["SDKForPandasLayer"]
            )

            for memory_config in MEMORY_CONFIGS:
                zip_layers_function_name = f"perf_zip_layers_{runtime_label}_{memory_config}"
                functions_by_name[zip_layers_function_name] = lamb.Function(
                    self,
                    zip_layers_function_name,
                    **common_function_kwargs,
                    environment={**common_envs, "POWERTOOLS_SERVICE_NAME": zip_layers_function_name},
                    code=lamb.Code.from_asset(path.join(path.dirname(__file__), "function")),
                    layers=[powertools_layer, sdk_for_pandas_layer],
                    handler="handler.handle_event",
                    runtime=runtime,
                    function_name=zip_layers_function_name,
                )
            
            image_code = lamb.DockerImageCode.from_image_asset(
                path.dirname(__file__),
                build_args={"PYTHON_VERSION": runtime_props["ImageVersion"]},
                platform=ecr_assets.Platform.LINUX_AMD64
            )
            for memory_config in MEMORY_CONFIGS:
                image_function_name = f"perf_image_{runtime_label}_{memory_config}"
                functions_by_name[image_function_name] = lamb.DockerImageFunction(
                    self,
                    image_function_name,
                    **common_function_kwargs,
                    environment={**common_envs, "POWERTOOLS_SERVICE_NAME": image_function_name},
                    code=image_code,
                    function_name=image_function_name,
                )

        for func in functions_by_name.values():
            func.role.add_to_principal_policy(iam.PolicyStatement(
                actions=["s3:PutObject"],
                resources=[f"{self.bucket.bucket_arn}/*"],
                effect=iam.Effect.ALLOW
            ))
            self.bucket.grant_read_write(func)

        return functions_by_name
    

    def create_dashboard(self, functions_by_name):
        dash = cloudwatch.Dashboard(
            self, "LambdaDatasciPerfDashboard", 
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
                cloudwatch.Metric(metric_name="ColdStart", namespace=POWERTOOLS_METRICS_NAMESPACE, dimensions_map={
                    "function_name": function_name, "service": function_name
                }, statistic=cloudwatch.Statistic.SUM.name, label=function_name)
                for function_name in sorted(functions_by_name.keys())
            ]
        ))

        dash.add_widgets(cloudwatch.SingleValueWidget(
            title="Lambda Invocations",
            set_period_to_time_range=True,
            width=24,
            height=6,
            metrics=[functions_by_name[function_name].metric_invocations(
                statistic=cloudwatch.Statistic.SUM.name, label=function_name
            ) for function_name in sorted(functions_by_name.keys())]
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
            ("p99", "pct(@initDuration, 99) as p99_init_duration"),
            ("max", "max(@initDuration) as max_init_duration"),
            ("avg", "avg(@initDuration) as avg_init_duration"),
            ("min", "min(@initDuration) as min_init_duration")
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

            dash.add_widgets(cloudwatch.LogQueryWidget(
                title=f"Module load times",
                log_group_names=[f.log_group.log_group_name for f in functions_by_name.values()],
                width=24,
                height=24,
                query_string="""
fields @timestamp, @message, @logStream, @log
| filter ispresent(timings.boto3)
| parse @log '/aws/lambda/*' as function_name
| filter function_name like 'Python39'
| parse function_name '_*_Python39_*' as pkg_method, mem_cfg
| stats
pct(timings.powertools_init_time, 95) / 1000 as powertools_init,
pct(timings.boto3_init_time, 95) / 1000  as boto3_init,
pct(timings.aws_lambda_powertools, 95) / 1000  as powertools,
pct(timings.base64, 95) / 1000  as base64,
pct(timings.boto3, 95) / 1000  as boto3,
pct(timings.datetime, 95) / 1000  as datetime,
pct(timings.json, 95) / 1000  as json,
pct(timings.numpy, 95) / 1000  as numpy,
pct(timings.os, 95) / 1000  as os,
pct(timings.pandas, 95) / 1000  as pandas,
pct(timings.pyarrow, 95) / 1000  as pyarrow,
pct(timings.pyarrow.parquet, 95) / 1000  as parquet,
pct(timings.sys, 95) / 1000  as sys
, (powertools_init + boto3_init + powertools + base64 + boto3 + datetime + json + numpy + os + pandas + pyarrow + parquet + sys) / 1000 as total_s
by
pkg_method, mem_cfg, 
bin(1h) as hour
| display pkg_method, mem_cfg, hour,
floor(pandas) as pandas_ms,
floor(numpy) as numpy_ms,
floor(pyarrow) as pyarrow_ms,
floor(parquet) as parquet_ms,
floor(boto3) as boto3_ms,
floor(powertools) as powertools_ms,
floor(powertools_init) as powertools_init_ms,
floor(boto3_init) as boto3_init_ms,
total_s
| sort pkg_method asc, mem_cfg asc, hour asc
""",
                view=cloudwatch.LogQueryVisualizationType.TABLE
            ))


        dash.add_widgets(cloudwatch.SingleValueWidget(
            title="Lambda Concurrent Executions",
            set_period_to_time_range=True,
            width=24,
            height=6,
            metrics=[functions_by_name[function_name].metric(
                statistic=cloudwatch.Statistic.MAXIMUM.name, label=function_name, metric_name="ConcurrentExecutions"
            ) for function_name in sorted(functions_by_name.keys())]
        ))

    def _service_name_from_function_name(self, function_name: str) -> str:
        return "_".join(function_name.split("_")[:-1])
