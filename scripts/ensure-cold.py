#!/usr/bin/env python3

from datetime import datetime
import sys

import boto3

def ensure_cold():
    session = boto3.session.Session()
    lamb = session.client("lambda")
    pag = lamb.get_paginator("list_functions")

    function_names = []

    for page in pag.paginate():
        function_names.extend([f["FunctionName"] for f in page["Functions"] if f["FunctionName"].startswith("perf_")])

    env_value = datetime.now().isoformat()
    envs = { "COLD_START_FORCER": env_value }
    for function_name in function_names:
        lamb.update_function_configuration(FunctionName=function_name, Environment={
            "Variables": envs
        })
        print(f"{function_name} updated with {envs}")


if __name__ == "__main__":
    ensure_cold()
