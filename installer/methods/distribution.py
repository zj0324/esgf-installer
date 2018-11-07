import logging
import os
import shutil
import tarfile
import zipfile

from backports import configparser
import requests

from .generic import Generic
from ..constants import INFO_FILE, UNIQUE_KEY
from ..utils import mkdir_p, chown_R

class FileManager(Generic):
    ''' Install file, git, and compressed components from a local or remote location '''
    def __init__(self, components):
        Generic.__init__(self, components)
        self.log = logging.getLogger(__name__)
        self.tmp = os.path.join(os.sep, "tmp")
        self.chunk_size = 1*1024
        parser = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
        parser.read(INFO_FILE)
        parser.add_section(UNIQUE_KEY)
        for component in self.components:
            try:
                is_tmpl = component["template"]
            except KeyError:
                is_tmpl = False

            if not is_tmpl:
                continue

            with open(component["source"], "r") as tmpl:
                tmpl_contents = tmpl.read()
                parser.set(UNIQUE_KEY, "content", tmpl_contents)
                component["content"] = parser.get(UNIQUE_KEY, "content")

    def _install(self, names):
        for component in self.components:
            if component["name"] not in names:
                continue

            if not os.path.isfile(component["source"]):
                source = self._get_remote(component)
            else:
                source = component["source"]

            filepath = self._extract(source, component)
            self._chown(component, filepath)
            self._chmod(component, filepath)

    def _chmod(self, component, filepath):
        try:
            mode = component["mode"]
        except KeyError:
            pass
        else:
            os.chmod(filepath, mode)

    def _chown(self, component, filepath):
        try:
            owner_user = component["owner_user"]
        except KeyError:
            owner_user = None
        try:
            owner_group = component["owner_group"]
        except KeyError:
            owner_group = None
        if owner_group is not None or owner_user is not None:
            chown_R(filepath, owner_user, owner_group)

    def _get_remote(self, component):
        url = component["source"]
        # Get the name of the remote file
        remote_file = url.rstrip("/").rsplit('/', 1)[-1]
        # Download to temp directory
        filename = os.path.join(self.tmp, remote_file)
        #if not os.path.isfile(filename):
        response = requests.get(url, stream=True)
        with open(filename, 'wb') as localfile:
            for chunk in response.iter_content(chunk_size=self.chunk_size):
                localfile.write(chunk)
        return filename

    def _extract(self, filepath, component):
        try:
            extract_file = component["extract"]
        except KeyError:
            extract_file = True
        if not os.path.isdir(filepath) and extract_file and tarfile.is_tarfile(filepath):
            if os.path.isdir(component["dest"]):
                shutil.rmtree(component["dest"])
            try:
                tar_root_dir = component["tar_root_dir"]
            except KeyError:
                mkdir_p(component["dest"])
                with tarfile.open(filepath) as archive:
                    archive.extractall(component["dest"])
            else:
                with tarfile.open(filepath) as archive:
                    archive.extractall(self.tmp)
                tmp_filepath = os.path.join(self.tmp, tar_root_dir)
                shutil.move(tmp_filepath, component["dest"])
            return component["dest"]
        elif not os.path.isdir(filepath) and extract_file and zipfile.is_zipfile(filepath):
            if os.path.isdir(component["dest"]):
                shutil.rmtree(component["dest"])
            mkdir_p(component["dest"])
            with zipfile.ZipFile(filepath, "r") as archive:
                archive.extractall(component["dest"])
            return component["dest"]
        elif os.path.isfile(filepath):
            dest_dir = os.path.dirname(component["dest"].rstrip(os.sep))
            mkdir_p(dest_dir)
            try:
                with open(component["dest"], "w") as dest:
                    dest.write(component["content"])
            except KeyError:
                shutil.copy(filepath, component["dest"])
            return component["dest"]

    def _versions(self):
        #TODO This only checks for existence of files, maybe do a little more, md5 checksum?
        versions = {}
        for component in self.components:
            if os.path.isfile(component["dest"]):
                versions[component["name"]] = "1"
            elif os.path.isdir(component["dest"]) and os.listdir(component["dest"]):
                versions[component["name"]] = "1"
            else:
                versions[component["name"]] = None
        return versions

    def _uninstall(self):
        for component in self.components:
            if os.path.isfile(component["dest"]):
                os.remove(component["dest"])
            elif os.path.isdir(component["dest"]):
                shutil.rmtree(component["dest"])
            else:
                self.log.info("%s not installed", component["name"])