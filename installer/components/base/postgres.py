
from ..syspkg import SysPkgComponent

class Postgres(SysPkgComponent):
    def __init__(self, name, config):
        SysPkgComponent.__init__(self, name, config)
