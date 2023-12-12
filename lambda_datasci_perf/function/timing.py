import time

class Timer:

    def __init__(self):
        self.time = 0
        self.elapsed_us = 0

    def __enter__(self):
        self.time = time.monotonic_ns()

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.elapsed_us = (time.monotonic_ns() - self.time) / 1000