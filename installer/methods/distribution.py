import logging
import os
import shutil
import tarfile
import zipfile

from plumbum import local
from plumbum import TEE
import requests

from ..utils import mkdir_p, chown_R
from .generic import Generic

class FileManager(Generic):
    ''' Install file, git, and compressed components from a local or remote location '''
    def __init__(self, components):
        Generic.__init__(self, components)
        self.log = logging.getLogger(__name__)
        self.tmp = os.path.join(os.sep, "tmp")
        self.chunk_size = 1*1024


    def _install(self, names):
        for component in self.components:
            if component.name not in names:
                continue

            if not os.path.isfile(component.source):
                source = self._get_remote(component)
            else:
                source = component.source

            filepath = self._extract(source, component)

            try:
                chown_R(filepath, component.owner_uid, component.owner_gid)
            except AttributeError:
                pass

    def _get_remote(self, component):
        url = component.source
        # Get the name of the remote file
        remote_file = url.rstrip("/").rsplit('/', 1)[-1]
        # If it is a git repository
        if remote_file.endswith(".git"):
            git = local["git"]
            args = ["clone", "--depth", "1"]
            try:
                args += ["--branch", component.tag]
            except AttributeError:
                pass
            filename = os.path.join(self.tmp, component.name)
            args += [component.source, filename]
            result = git.__getitem__(args) & TEE
        # If it is just a file
        else:
            filename = os.path.join(self.tmp, remote_file)
            #if not os.path.isfile(filename):
            response = requests.get(url, stream=True)
            with open(filename, 'wb') as localfile:
                for chunk in response.iter_content(chunk_size=self.chunk_size):
                    localfile.write(chunk)
        return filename

    def _extract(self, filepath, component):
        try:
            extract_file = component.extract
        except AttributeError:
            extract_file = True
        if not os.path.isdir(filepath) and extract_file and tarfile.is_tarfile(filepath):
            try:
                tar_root_dir = component.tar_root_dir
            except AttributeError:
                with tarfile.open(filepath) as archive:
                    archive.extractall(component.dest)
            else:
                with tarfile.open(filepath) as archive:
                    archive.extractall(self.tmp)
                tmp_filepath = os.path.join(self.tmp, tar_root_dir)
                shutil.move(tmp_filepath, component.dest)
            return component.dest
        elif not os.path.isdir(filepath) and extract_file and zipfile.is_zipfile(filepath):
            with zipfile.ZipFile(filepath, "r") as archive:
                archive.extractall(component.dest)
            return component.dest
        else:
            # Not a tar or zip file or do not extract
            dest_dir, dest_file = os.path.split(component.dest)
            mkdir_p(dest_dir)
            shutil.move(filepath, component.dest)
            return component.dest

    def _versions(self):
        #TODO This only checks for existence of files, maybe do a little more, md5 checksum?
        versions = {}
        for component in self.components:
            if os.path.isfile(component.dest):
                versions[component.name] = "1"
            elif os.path.isdir(component.dest) and os.listdir(component.dest):
                versions[component.name] = "1"
            else:
                versions[component.name] = None
        return versions

    def _uninstall(self):
        for component in self.components:
            if os.path.isfile(component.dest):
                os.remove(component.dest)
            elif os.path.isdir(component.dest):
                shutil.rmtree(component.dest)
            else:
                self.log.info("%s not installed", component.name)