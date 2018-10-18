import logging

from ..install_codes import OK, NOT_INSTALLED, BAD_VERSION

class Generic(object):
    def __init__(self, components):
        self.log = logging.getLogger(__name__)
        self.components = components

    def uninstall(self):
        self._uninstall()

    def _uninstall(self):
        ''' Generic version, should be reimplemented by children '''
        pass

    def install(self, names):
        ''' Entry function to perform an installation '''
        self._install(names)

    def _install(self, names):
        ''' Generic version, should be reimplemented by children '''
        pass

    def statuses(self):
        ''' Entry function to get the statuses '''
        return self._statuses()

    def _statuses(self):
        ''' As long as versions is implemented correctly this is all that a status check is '''
        versions = self.versions()
        statuses = {}
        for component in self.components:
            name = component["name"]
            version = versions[name]
            if version is None:
                statuses[name] = NOT_INSTALLED
            else:
                try:
                    statuses[name] = OK if component["version"] == version else BAD_VERSION
                except KeyError:
                    statuses[name] = OK
        return statuses

    def versions(self):
        ''' Entry function to get versions '''
        return self._versions()

    def _versions(self):
        ''' Generic version, should be reimplemented by children '''
        versions = {}
        for component in self.components:
            versions[component.name] = component.version()
        return versions