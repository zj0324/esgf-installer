import os
import os.path as path

from .controllers.service import Service
from .methods.command import Command
from .methods.conda import Conda
from .methods.distribution import FileManager
from .methods.easy_install import EasyInstall
from .methods.git import Git
from .methods.package_manager import PackageManager, Pip
from .methods.users_groups import UserMethod, GroupMethod

_FILE_DIR = path.join(path.dirname(__file__), "files")

_BASE = {
    "httpd": {
        "method": PackageManager,
        "controller": Service
    },
    "esgf-httpd.conf": {
        "method": FileManager,
        "requires": ["httpd"],
        "source": path.join(_FILE_DIR, "httpd", "${name}"),
        "dest": path.join(os.sep, "etc", "httpd", "conf", "httpd.conf")
    },
    "esgf-ca-bundle.crt": {
        "method": FileManager,
        "source": path.join(_FILE_DIR, "httpd", "${name}"),
        "dest": path.join(os.sep, "etc", "certs", "${name}")
    },
    "postgres": {
        "method": PackageManager,
        "controller": Service,
        "service_name": "postgresql",
        "version": "8.4.20",
        "yum": "postgresql-server-${version}"
    },
    "postgres-init": {
        "method": Command,
        "requires": ["postgres"],
        "command": "service",
        "args": ["postgresql", "initdb"]
    },
    "postgresql.conf": {
        "method": FileManager,
        "requires": ["postgres-init"],
        "source": path.join(_FILE_DIR, "postgres", "${name}"),
        "dest": path.join(os.sep, "var", "lib", "pgsql", "data", "${name}"),
        "owner_user": "postgres",
        "owner_group": "postgres"
    },
    "pg_hba.conf": {
        "method": FileManager,
        "requires": ["postgres-init"],
        "source": path.join(_FILE_DIR, "postgres", "${name}"),
        "dest": path.join(os.sep, "var", "lib", "pgsql", "data", "${name}"),
        "owner_user": "postgres",
        "owner_group": "postgres"
    },
    "java": {
        "method": PackageManager,
        "version": "1.8.0",
        "yum": "java-${version}-openjdk"
    },
    "postgresql-devel": {
        "method": PackageManager
    },
    "httpd-devel": {
        "method": PackageManager
    },
    "mod_ssl": {
        "method": PackageManager
    },
    # "sqlite-devel": {
    #     "method": PackageManager
    # },
    # "freetype-devel": {
    #     "method": PackageManager
    # },
    # "curl-devel": {
    #     "method": PackageManager
    # },
    # "bison": {
    #     "method": PackageManager
    # },
    # "file": {
    #     "method": PackageManager
    # },
    # "flex": {
    #     "method": PackageManager
    # },
    # "uuid-devel": {
    #     "method": PackageManager
    # },
    # "libtool": {
    #     "method": PackageManager
    # },
    # "gettext-devel": {
    #     "method": PackageManager
    # },
    # "libuuid-devel": {
    #     "method": PackageManager
    # },
    # "libxml2": {
    #     "method": PackageManager
    # },
    # "libxml2-devel": {
    #     "method": PackageManager
    # },
    # "libxslt": {
    #     "method": PackageManager
    # },
    # "libxslt-devel": {
    #     "method": PackageManager
    # },
    # "lsof": {
    #     "method": PackageManager
    # },
    # "openssl-devel": {
    #     "method": PackageManager
    # },
    # "pam-devel": {
    #     "method": PackageManager
    # },
    # "pax": {
    #     "method": PackageManager
    # },
    # "tk-devel": {
    #     "method": PackageManager
    # },
    # "zlib-devel": {
    #     "method": PackageManager
    # },
    # "perl-Archive-Tar": {
    #     "method": PackageManager
    # },
    # "perl-XML-Parser": {
    #     "method": PackageManager
    # },
    # "libX11-devel": {
    #     "method": PackageManager
    # },
    # "libtool-ltdl-devel": {
    #     "method": PackageManager
    # },
    # "e2fsprogs-devel": {
    #     "method": PackageManager
    # },
    # "gcc-gfortran": {
    #     "method": PackageManager
    # },
    # "libicu-devel": {
    #     "method": PackageManager
    # },
    # "libgtextutils-devel": {
    #     "method": PackageManager
    # },
    # "libjpeg-turbo-devel": {
    #     "method": PackageManager
    # },
    # "*ExtUtils*": {
    #     "method": PackageManager
    # },
    # "readline-devel": {
    #     "method": PackageManager
    # },
    "tomcat-group": {
        "method": GroupMethod,
        "groupname": "tomcat"
    },
    "tomcat-user": {
        "method": UserMethod,
        "requires": ["tomcat-group"],
        "options": ["-s", "/sbin/nologin", "-g", "tomcat", "-d", "/usr/local/tomcat"],
        "username": "tomcat"
    },
    "tomcat": {
        "method": FileManager,
        "requires": ["tomcat-user", "tomcat-group"],
        "version": "8.5.20",
        "source": "http://archive.apache.org/dist/tomcat/tomcat-8/v${version}/bin/apache-tomcat-${version}.tar.gz",
        "dest": "/tmp/tomcat",
        "tar_root_dir": "apache-tomcat-${version}",
        "owner_user": "tomcat",
        "owner_group": "tomcat"
    }
    # "esgf-config-git": {
    #     "method": Git,
    #     "source": "https://github.com/ESGF/esgf-config.git",
    #     "dest": "/tmp/esgf-config"
    # }
}
_DATA = {
    "thredds": {
        "method": FileManager,
        "version": "5.0.2",
        "source": "${ESGF_PARAMS:mirror}/2.6/8/thredds/5.0/${version}/thredds.war",
        "dest": "/tmp/thredds"
    },
    "esgf-dashboard-git": {
        "method": Git,
        "tag": "v1.5.20",
        "source": "https://github.com/ESGF/esgf-dashboard.git",
        "dest": "/tmp/esgf-dashboard"
    },
    "cdutil": {
        "method": Conda,
        "channels": ["conda-forge"]
    },
    "cmor": {
        "method": Conda,
        "channels": ["conda-forge"]
    },
    "esgcet": {
        "method": Pip,
        "requires": ["postgres", "postgresql-devel"],
        "version": "3.5.0",
        "tag": "v${version}",
        "repo": "https://github.com/ESGF/esg-publisher.git",
        "egg": "${name}",
        "subdirectory": "src/python/esgcet",
        "pip_name": "git+${repo}@${tag}#egg=${egg}&subdirectory=${subdirectory}"
    },
    "esgf-dashboard": {
        "method": EasyInstall,
        "version": "0.0.2",
        "source": "${ESGF_PARAMS:mirror}/2.6/8/esgf-dashboard/esgf_dashboard-${version}-py2.7.egg",
        "dest": "/tmp/esgf_dashboard/esgf_dashboard.egg",
        "extract": False,
        "conda_env": "test-env"
    },
    "esgf-node-manager": {
        "method": EasyInstall,
        "version": "0.1.5",
        "source": "${ESGF_PARAMS:mirror}/2.6/8/esgf-node-manager/esgf_node_manager-${version}-py2.7.egg",
        "dest": "/tmp/esgf_node_manager/esgf_node_manager.egg",
        "extract": False
    }
}
_INDEX = {
    "cog": {
        "method": Git,
        "requires": ["httpd"],
        "source": "https://github.com/William-Hill/COG.git",
        "dest": path.join(os.sep, "usr", "local", "cog", "cog-install"),
        "tag": "ESGF_3.0",
        "owner_user": "apache",
        "owner_group": "apache"
    },
    "cog-requirements": {
        "method": Command,
        "requires": ["cog"],
        "command": "pip",
        "args": ["-r", "requirements.txt"],
        "working_dir": "${cog:dest}"
    },
    "cog-setup-install": {
        "method": Command,
        "requires": ["cog"],
        "command": "python",
        "args": ["setup.py", "install"],
        "working_dir": "${cog:dest}"
    },
    "cog-setup-setup": {
        "method": Command,
        "requires": ["cog"],
        "command": "python",
        "args": ["setup.py", "setup_cog", "--esgf=true"],
        "working_dir": "${cog:dest}"
    },
    "cog-setup-manage": {
        "method": Command,
        "requires": ["cog"],
        "command": "python",
        "args": ["manage.py", "collectstatic", "--no-input"],
        "working_dir": "${cog:dest}"
    },
    "transfer_api_client_python": {
        "method": Git,
        "requires": ["cog"],
        "source": "https://github.com/globusonline/transfer-api-client-python.git",
        "dest": path.join(os.sep, "usr", "local", "cog", "transfer-api-client-python")
    },
    "make_transfer_api_client": {
        "method": Command,
        "requires": ["transfer_api_client_python"],
        "command": "make",
        "working_dir": "${transfer_api_client_python:dest}"
    },
    "install_transfer_api_client": {
        "method": Command,
        "requires": ["make_transfer_api_client"],
        "command": "make",
        "args": ["install"],
        "working_dir": "${transfer_api_client_python:dest}"
    },
    "mod-wsgi": {
        "method": Pip,
        "requires": ["httpd"],
        "version": "4.5.3",
        "pip_name": "${name}==${version}"
    },
    "django-openid-auth": {
        "method": Pip,
        "repo": "https://github.com/EarthSystemCoG/django-openid-auth.git",
        "egg": "${name}",
        "pip_name": "git+${repo}#egg=${egg}"
    }
}
_TEST = {
    "plumbum": {
        "method": Pip,
        "conda_env": "test-env"
    },
    "pyopenssl": {
        "method": Conda,
        "conda_env": "test-env",
    },
    "echo-env-command": {
        "method": Command,
        "command": "echo",
        "args": ["$CONDA_PREFIX"],
        "conda_env": "test-env"
    }
}
ALL = {
    "base": _BASE,
    "data": _DATA,
    "index": _INDEX,
    "test": _TEST
}