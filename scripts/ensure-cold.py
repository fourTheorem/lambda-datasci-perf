#!/usr/bin/env python3

from datetime import datetime
import sys

import boto3

def ensure_cold():
    session = boto3.session.Session()
    print('Using region', session.region_name)
    lamb = session.client("lambda")
    pag = lamb.get_paginator("list_functions")

    function_envs_by_name = {}

    for page in pag.paginate():
        function_envs_by_name.update({f["FunctionName"]: f["Environment"]["Variables"] for f in page["Functions"] if f["FunctionName"].startswith("perf_")})

    env_value = datetime.now().isoformat()
    added_envs = {"COLD_START_FORCER": env_value}
    for function_name, envs in function_envs_by_name.items():
        new_envs = {**envs, **added_envs}
        print('Updating', function_name, 'with', new_envs)
        lamb.update_function_configuration(FunctionName=function_name, Environment={"Variables": new_envs})


if __name__ == "__main__":
    ensure_cold()
