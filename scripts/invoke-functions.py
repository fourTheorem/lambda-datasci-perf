#!/usr/bin/env python3

import sys

import boto3
from tqdm import tqdm

from concurrent.futures import ThreadPoolExecutor, wait

def invoke_functions(count_per_function):
    session = boto3.session.Session()
    print(f"Using region {session.region_name}")
    lamb = session.client("lambda")
    pag = lamb.get_paginator("list_functions")

    function_names = []

    for page in pag.paginate():
        function_names.extend([f["FunctionName"] for f in page["Functions"] if f["FunctionName"].startswith("perf_") and "_measure_" not in f["FunctionName"]])

    progs = {}
    for function_name in function_names:
        bar = tqdm(range(0, count_per_function))
        bar.set_description(function_name)
        progs[function_name] = bar

    def perform_invocations(function_name):
        for _ in progs[function_name]:
            lamb.invoke_async(FunctionName=function_name, InvokeArgs=b"{}")

    futs = []
    with ThreadPoolExecutor(max_workers=len(function_names)) as ex:
        for function_name in function_names:
            futs.append(ex.submit(perform_invocations, function_name))

    wait(futs)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python invoke-functions.py <num_messages_per_function>")
    else:
        try:
            num_messages = int(sys.argv[1])
            invoke_functions(num_messages)
        except ValueError:
            print("Please provide a valid integer for the number of messages.")
