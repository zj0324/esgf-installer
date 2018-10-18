import logging

from plumbum import local
from plumbum import TEE

from ..methods.generic import Generic

class Service(Generic):
    def __init__(self, name, config):
        Generic.__init__(self, [config])
        config = self.components[0]
        self.log = logging.getLogger(__name__)
        self.service = local["service"]
        self.start_arg = ["start"]
        self.stop_arg = ["stop"]
        self.restart_arg = ["restart"]
        try:
            self.service_name = config["service_name"]
        except KeyError:
            self.service_name = name

    def start(self):
        args = [self.service_name] + self.start_arg
        self.service.__getitem__(args) & TEE

    def stop(self):
        args = [self.service_name] + self.stop_arg
        self.service.__getitem__(args) & TEE

    def restart(self):
        args = [self.service_name] + self.restart_arg
        self.service.__getitem__(args) & TEE