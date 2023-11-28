from timing import Timer

class ImportTimer:
    def __init__(self):
        self.timings = {}

    def import_module(self, module_name: str):
        timer = Timer()
        with timer:
            mod = __import__(module_name)
        self.timings[module_name] = timer.elapsed_us
        return mod