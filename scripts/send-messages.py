#!/usr/bin/env python3

import sys
from datetime import datetime
import boto3

def send_messages(message_count):
    session = boto3.session.Session()
    sqs_client = session.client("sqs")

    batch_ts = datetime.now().strftime("%Y%m%d%H%M%S")
    BATCH_SIZE = 10

    queue_url = [u for u in sqs_client.list_queues()["QueueUrls"] if 'LambdaDatasciPerfQueue' in u][0]

    for idx in range(1, message_count + 1, BATCH_SIZE):
        end_idx = min(idx + BATCH_SIZE, message_count + 1)
        rng = range(idx, end_idx)
        print(f"Sending messages {rng.start} to {rng.stop - 1}... ", end="\t")
        response = sqs_client.send_message_batch(
            QueueUrl=queue_url,
            Entries=[{
                "Id": f"{batch_ts}-{msg_idx}",
                "MessageBody": "Hello"
            } for msg_idx in rng]
        )
        failed_count = len(response["Failed"])
        successful_count = len(response["Successful"])
        print(f"{failed_count} failed, {successful_count} succeeded")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py <num_messages>")
    else:
        try:
            num_messages = int(sys.argv[1])
            send_messages(num_messages)
        except ValueError:
            print("Please provide a valid integer for the number of messages.")
