import os
import shutil
import pwd
import grp
import psutil
import signal
import logging
import glob
import ConfigParser
import requests
import yaml
from clint.textui import progress
from esgf_utilities import esg_functions
from esgf_utilities import pybash
from esgf_utilities import esg_property_manager
from plumbum.commands import ProcessExecutionError

current_directory = os.path.join(os.path.dirname(__file__))

logger = logging.getLogger("esgf_logger" +"."+ __name__)

with open(os.path.join(os.path.dirname(__file__), os.pardir, 'esg_config.yaml'), 'r') as config_file:
    config = yaml.load(config_file)

def download_solr_tarball(solr_tarball_url, SOLR_VERSION):
    print "\n*******************************"
    print "Download Solr version {SOLR_VERSION}".format(SOLR_VERSION=SOLR_VERSION)
    print "******************************* \n"
    r = requests.get(solr_tarball_url)

    path = '/tmp/solr-{SOLR_VERSION}.tgz'.format(SOLR_VERSION=SOLR_VERSION)
    with open(path, 'wb') as f:
        total_length = int(r.headers.get('content-length'))
        for chunk in progress.bar(r.iter_content(chunk_size=1024), expected_size=(total_length/1024) + 1):
            if chunk:
                f.write(chunk)
                f.flush()

def extract_solr_tarball(solr_tarball_path, SOLR_VERSION, target_path="/usr/local"):
    '''Extract the solr tarball to {target_path} and symlink it to /usr/local/solr'''
    print "\n*******************************"
    print "Extracting Solr"
    print "******************************* \n"

    with pybash.pushd(target_path):
        esg_functions.extract_tarball(solr_tarball_path)
        os.remove(solr_tarball_path)
        pybash.symlink_force("solr-{SOLR_VERSION}".format(SOLR_VERSION=SOLR_VERSION), "solr")

def download_template_directory():
    '''download template directory structure for shards home'''
    esg_dist_url = esg_property_manager.get_property("esg.dist.url")
    with pybash.pushd("/usr/local/src"):
        r = requests.get("{}/esg-search/solr-home.tar".format(esg_dist_url))

        path = 'solr-home.tar'
        with open(path, 'wb') as f:
            total_length = int(r.headers.get('content-length'))
            for chunk in progress.bar(r.iter_content(chunk_size=1024), expected_size=(total_length/1024) + 1):
                if chunk:
                    f.write(chunk)
                    f.flush()

        esg_functions.extract_tarball("/usr/local/src/solr-home.tar")


def start_solr(solr_config_type, port_number, SOLR_INSTALL_DIR="/usr/local/solr", SOLR_HOME="/usr/local/solr-home"):
    print "\n*******************************"
    print "Starting Solr"
    print "******************************* \n"
    # -f starts solr in the foreground; -d Defines a server directory;
    # -s Sets the solr.solr.home system property; -p Start Solr on the defined port;
    # -a Start Solr with additional JVM parameters,
    # -m Start Solr with the defined value as the min (-Xms) and max (-Xmx) heap size for the JVM

    if solr_config_type == "master":
        enable_nodes = "-Denable.master=true"
    elif solr_config_type == "localhost":
        enable_nodes = "-Denable.localhost=true"
    else:
        enable_nodes = "-Denable.master=true -Denable.slave=true"

    server_directory = "{}/server".format(SOLR_INSTALL_DIR)
    solr_solr_home = "{}/{}-{}".format(SOLR_HOME, solr_config_type, port_number)
    start_solr_options = ["start", "-d", server_directory, "-s", solr_solr_home, "-p", port_number, "-a", enable_nodes, "-m", "512m"]
    esg_functions.call_binary("/usr/local/solr/bin/solr", start_solr_options)

def solr_status():
    '''Check the status of solr'''
    try:
        result = esg_functions.call_binary("/usr/local/solr/bin/solr", ["status"])
    except ProcessExecutionError as error:
        # 3 is the return code if not running
        if error.retcode==3:
            return False
        raise
    return True

#TODO: fix and test
def check_solr_process(solr_config_type="master", port=8984):
    try:
        solr_pid = [proc for proc in psutil.net_connections() if proc.laddr.port == port][0].pid
        print " Solr process for {solr_config_type} running on port [{solr_server_port}] with pid {solr_pid}".format(solr_config_type, port, solr_pid)
        return True
    except:
        print "Solr not running"
        return False

def stop_solr(SOLR_INSTALL_DIR="/usr/local/solr", port="-all"):
    '''Stop the solr process'''
    try:
        esg_functions.call_binary("/usr/local/solr/bin/solr", ["stop", port])
    except ProcessExecutionError:
        logger.error("Could not stop solr with control script. Killing with PID")
        solr_pid_files = glob.glob("/usr/local/solr/bin/*.pid")
        for pid in solr_pid_files:
            solr_pid = open(pid, "r").read()
            if psutil.pid_exists(int(solr_pid)):
                try:
                    os.kill(int(solr_pid), signal.SIGKILL)
                except OSError:
                    logger.error("Could not kill solr process with pid %s", solr_pid)
                    raise
    except OSError:
        pass

    solr_status()


def commit_shard_config(config_type, port_number, config_file="/esg/config/esgf_shards.config"):
    parser = ConfigParser.SafeConfigParser()
    parser.read(config_file)

    try:
        parser.add_section("esgf_solr_shards")
    except ConfigParser.DuplicateSectionError:
        logger.debug("section already exists")

    parser.set("esgf_solr_shards", config_type, port_number)
    with open(config_file, "w") as config_file_object:
        parser.write(config_file_object)

def read_shard_config(config_file="/esg/config/esgf_shards.config"):
    parser = ConfigParser.SafeConfigParser()
    parser.readfp(open(config_file))
    return parser.items("esgf_solr_shards")

def add_shards(config_type, port_number=None):
    print "\n*******************************"
    print "Adding Shards"
    print "******************************* \n"
    if config_type == "master":
        port_number = "8984"
    elif config_type == "slave":
        port_number = "8983"

    esg_functions.stream_subprocess_output("/usr/local/bin/add_shard.sh {} {}".format(config_type, port_number))

    commit_shard_config(config_type, port_number)


def write_solr_install_log(solr_config_type, solr_version, solr_install_dir):
    if solr_config_type == "master" or solr_config_type == "slave":
        esg_functions.write_to_install_manifest("esg_search:solr-{}".format(solr_config_type), solr_install_dir, solr_version)

'''
    Install solr flow:
    solr_config_types = ["master", "slave"]
    for config in solr_config_types:
        add_shard(config)


    add_shard(config_type):
        checks if config_type is already in esgf_shards_config_file (/esg/config/esgf_shards.config)
        if config_type is not "master" or "slave"; attempts to ping url http://${config_type%:*}:${target_index_search_port}/solr

        calls setup_solr(config_type)
        calls configure_solr()
        calls write_solr_install_log()
        calls _commit_configuration()

    setup_solr(config_type):
        calls solr_init(config_type) which Stupidly sets a bunch of global variables
        checks for existing solr-home installation
        Checks to see if a shard already exists on config_type's port
        Checks if solr is already installed, otherwise download it

    def solr_init(config_type, config_port=None):
        sets solr_config_type, solr_server_port, solr_install_dir, solr_data_dir, solr_server_dir, solr_logs_dir as global variables smh
    configure_solr():
        solr_init(config_type)

        loop through solr cores and update solr_config_files

'''

def setup_solr(index_config, SOLR_INSTALL_DIR="/usr/local/solr", SOLR_HOME="/usr/local/solr-home", SOLR_DATA_DIR = "/esg/solr-index"):
    '''Setup Apache Solr for faceted search'''
    if os.path.isdir("/usr/local/solr"):
        print "Solr directory found."
        try:
            setup_solr_answer = esg_property_manager.get_property("update.solr")
        except ConfigParser.NoOptionError:
            setup_solr_answer = raw_input(
                "Do you want to contine the Solr installation [y/N]: ") or "no"
        if setup_solr_answer.lower() in ["no", "n"]:
            print "Using existing Solr setup. Skipping installation"
            return False

    print "\n*******************************"
    print "Setting up Solr"
    print "******************************* \n"

    # # Solr/Jetty web application
    SOLR_VERSION = "5.5.5"
    os.environ["SOLR_HOME"] = SOLR_HOME
    SOLR_INCLUDE= "{SOLR_HOME}/solr.in.sh".format(SOLR_HOME=SOLR_HOME)
    solr_config_types = index_config

    #Download solr tarball
    solr_tarball_url = "http://archive.apache.org/dist/lucene/solr/{SOLR_VERSION}/solr-{SOLR_VERSION}.tgz".format(SOLR_VERSION=SOLR_VERSION)
    download_solr_tarball(solr_tarball_url, SOLR_VERSION)
    #Extract solr tarball
    solr_extract_to_path = SOLR_INSTALL_DIR.rsplit("/",1)[0]
    extract_solr_tarball('/tmp/solr-{SOLR_VERSION}.tgz'.format(SOLR_VERSION=SOLR_VERSION), SOLR_VERSION, target_path=solr_extract_to_path)

    pybash.mkdir_p(SOLR_DATA_DIR)

    # download template directory structure for shards home
    download_template_directory()

    pybash.mkdir_p(SOLR_HOME)

    # create non-privilged user to run Solr server
    esg_functions.add_unix_group("solr")

    useradd_options = ["-s", "/sbin/nologin", "-g", "solr", "-d", "/usr/local/solr", "solr"]
    try:
        esg_functions.call_binary("useradd", useradd_options)
    except ProcessExecutionError, err:
        if err.retcode == 9:
            pass
        else:
            raise

    SOLR_USER_ID = pwd.getpwnam("solr").pw_uid
    SOLR_GROUP_ID = grp.getgrnam("solr").gr_gid
    esg_functions.change_ownership_recursive("/usr/local/solr-{SOLR_VERSION}".format(SOLR_VERSION=SOLR_VERSION), SOLR_USER_ID, SOLR_GROUP_ID)
    esg_functions.change_ownership_recursive(SOLR_HOME, SOLR_USER_ID, SOLR_GROUP_ID)
    esg_functions.change_ownership_recursive(SOLR_DATA_DIR, SOLR_USER_ID, SOLR_GROUP_ID)

    #Copy shard files
    shutil.copyfile(os.path.join(current_directory, "solr_scripts/add_shard.sh"), "/usr/local/bin/add_shard.sh")
    shutil.copyfile(os.path.join(current_directory, "solr_scripts/remove_shard.sh"), "/usr/local/bin/remove_shard.sh")

    os.chmod("/usr/local/bin/add_shard.sh", 0555)
    os.chmod("/usr/local/bin/remove_shard.sh", 0555)

    # add shards
    for config_type in solr_config_types:
        logger.debug("config_type: %s", config_type)
        add_shards(config_type)
        write_solr_install_log(config_type, SOLR_VERSION, SOLR_INSTALL_DIR)

    # custom logging properties
    shutil.copyfile(os.path.join(current_directory, "solr_scripts/log4j.properties"), "{SOLR_INSTALL_DIR}/server/resources/log4j.properties".format(SOLR_INSTALL_DIR=SOLR_INSTALL_DIR))
    pybash.mkdir_p("/esg/solr-logs")


def main(index_config):
    setup_solr(index_config)

if __name__ == '__main__':
    main(index_config=config["index_config"])
