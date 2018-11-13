'''
Tomcat Management Functions
'''
import os
import shutil
import grp
import pwd
import errno
import logging
import ConfigParser
import sys
import signal
from time import sleep
import yaml
import requests
import psutil
from lxml import etree
from clint.textui import progress
from esgf_utilities.esg_exceptions import SubprocessError
from esgf_utilities import esg_functions
from esgf_utilities import pybash
from esgf_utilities import esg_property_manager, esg_keystore_manager, esg_truststore_manager
from esgf_utilities import CA
from esgf_utilities.esg_env_manager import EnvWriter
from plumbum.commands import ProcessExecutionError

LOGGER = logging.getLogger("esgf_logger" + "." + __name__)
CURRENT_DIRECTORY = os.path.join(os.path.dirname(__file__))

with open(os.path.join(CURRENT_DIRECTORY, os.pardir, 'esg_config.yaml'), 'r') as config_file:
    CONFIG = yaml.load(config_file)

TOMCAT_VERSION = "8.5.20"
CATALINA_HOME = "/usr/local/tomcat"


def check_tomcat_version():
    '''Check installed tomcat version'''
    esg_functions.stream_subprocess_output("/usr/local/tomcat/bin/version.sh")


def download_tomcat():
    '''Download tomcat from distribution mirror'''
    if os.path.isdir("/usr/local/tomcat"):
        print "Tomcat directory found."
        check_tomcat_version()
        try:
            setup_tomcat_answer = esg_property_manager.get_property("update.tomcat")
        except ConfigParser.NoOptionError:
            setup_tomcat_answer = raw_input(
                "Do you want to contine the Tomcat installation [y/N]: ") or "no"

        if setup_tomcat_answer.lower() in ["no", "n"]:
            return False

    tomcat_download_url = "http://archive.apache.org/dist/tomcat/tomcat-8/v8.5.20/bin/apache-tomcat-8.5.20.tar.gz"
    print "downloading Tomcat"
    response = requests.get(tomcat_download_url)
    tomcat_download_path = "/tmp/apache-tomcat-{TOMCAT_VERSION}.tar.gz".format(
        TOMCAT_VERSION=TOMCAT_VERSION)
    with open(tomcat_download_path, 'wb') as tomcat_file:
        total_length = int(response.headers.get('content-length'))
        for chunk in progress.bar(response.iter_content(chunk_size=1024), expected_size=(total_length / 1024) + 1):
            if chunk:
                tomcat_file.write(chunk)
                tomcat_file.flush()

    return True

def remove_default_error_page():
    '''Removes the default Tomcat error page.
    From https://www.owasp.org/index.php/Securing_tomcat:
    The default error page shows a full stacktrace which is a disclosure of sensitive information. Place the following within the web-app tag (after the welcome-file-list tag is fine). The following solution is not ideal as it produces a blank page because Tomcat cannot find the file specified, but without a better solution this, at least, achieves the desired result. A well configured web application will override this default in CATALINA_HOME/webapps/APP_NAME/WEB-INF/web.xml so it won't cause problems.'''

    tree = etree.parse("/usr/local/tomcat/conf/web.xml")
    root = tree.getroot()
    error_subelement = etree.SubElement(root, "error-page")
    exception_subelement = etree.SubElement(error_subelement, "exception-type")
    exception_subelement.text = "java.lang.Throwable"
    location_subelement = etree.SubElement(error_subelement, "location")
    location_subelement.text = "/error.jsp"
    tree.write(open("/usr/local/tomcat/conf/web.xml", "w"), pretty_print=True, encoding='utf-8', xml_declaration=True)

def extract_tomcat_tarball(dest_dir="/usr/local"):
    '''Extract tomcat tarball that was downloaded from the distribution mirror'''
    with pybash.pushd(dest_dir):
        esg_functions.extract_tarball(
            "/tmp/apache-tomcat-{TOMCAT_VERSION}.tar.gz".format(TOMCAT_VERSION=TOMCAT_VERSION))

        # Create symlink
        pybash.symlink_force(
            "/usr/local/apache-tomcat-{}".format(TOMCAT_VERSION), "/usr/local/tomcat")
        try:
            os.remove(
                "/tmp/apache-tomcat-{TOMCAT_VERSION}.tar.gz".format(TOMCAT_VERSION=TOMCAT_VERSION))
        except OSError, error:
            LOGGER.error(error)

        #From https://www.owasp.org/index.php/Securing_tomcat
        tomcat_user_id = pwd.getpwnam("tomcat").pw_uid
        tomcat_group_id = grp.getgrnam("tomcat").gr_gid
        os.chown("/usr/local/tomcat", tomcat_user_id, tomcat_group_id)

        esg_functions.change_permissions_recursive("/usr/local/tomcat/conf", 0400)
        esg_functions.change_permissions_recursive("/usr/local/tomcat/logs", 0300)
        remove_default_error_page()



def remove_example_webapps():
    '''remove Tomcat example applications'''
    with pybash.pushd("/usr/local/tomcat/webapps"):
        webapps = os.listdir("/usr/local/tomcat/webapps")
        for webapp in webapps:
            try:
                shutil.rmtree(webapp)
            except OSError, error:
                if error.errno == errno.ENOENT:
                    pass
                else:
                    raise

def copy_config_files():
    '''copy custom configuration
    context.xml: increases the Tomcat cache to avoid flood of warning messages'''

    print "\n*******************************"
    print "Copying custom Tomcat config files"
    print "******************************* \n"
    try:
        shutil.copyfile(os.path.join(CURRENT_DIRECTORY, "tomcat_conf/context.xml"), "/usr/local/tomcat/conf/context.xml")
        pybash.mkdir_p("/esg/config/tomcat")

        shutil.copyfile(os.path.join(CURRENT_DIRECTORY, "tomcat_conf/tomcat-users.xml"), "/esg/config/tomcat/tomcat-users.xml")
        tomcat_user_id = pwd.getpwnam("tomcat").pw_uid
        tomcat_group_id = grp.getgrnam("tomcat").gr_gid
        os.chown("/esg/config/tomcat/tomcat-users.xml", tomcat_user_id, tomcat_group_id)

        shutil.copy(os.path.join(CURRENT_DIRECTORY, "tomcat_conf/setenv.sh"), os.path.join(CATALINA_HOME, "bin"))
    except OSError, error:
        print "Could not copy tomcat certs.", error
        LOGGER.exception()
        sys.exit()



def create_tomcat_group():
    '''Creates Tomcat Unix group'''
    try:
        esg_functions.call_binary("groupadd", ["tomcat"])
    except ProcessExecutionError, err:
        if err.retcode == 9:
            pass
        else:
            raise
    else:
        print "Created tomcat group with group id: {}".format(grp.getgrnam("tomcat").gr_gid)

def create_tomcat_user():
    '''Create the Tomcat system user and user group'''
    print "\n*******************************"
    print "Creating Tomcat User"
    print "******************************* \n"

    if "tomcat" in esg_functions.get_user_list():
        LOGGER.info("Tomcat user already exists")
        return

    if not "tomcat" in esg_functions.get_group_list():
        create_tomcat_group()

    useradd_options = ["-s", "/sbin/nologin", "-M", "-g", "tomcat", "-d", "/usr/local/tomcat", "tomcat"]
    esg_functions.add_unix_user(useradd_options)

    tomcat_directory = "/usr/local/apache-tomcat-{TOMCAT_VERSION}".format(
        TOMCAT_VERSION=TOMCAT_VERSION)
    tomcat_user_id = pwd.getpwnam("tomcat").pw_uid
    tomcat_group_id = grp.getgrnam("tomcat").gr_gid
    esg_functions.change_ownership_recursive(tomcat_directory, tomcat_user_id, tomcat_group_id)


def start_tomcat():
    '''Start tomcat server'''
    print "\n*******************************"
    print "Attempting to start Tomcat"
    print "******************************* \n"

    # This is used by esgf security/node_manager to find the properties file and password files
    os.environ["ESGF_HOME"] = CONFIG["esg_root_dir"]

    if check_tomcat_status():
        print "Tomcat already running"
        return
    try:
        esg_functions.stream_subprocess_output("/usr/local/tomcat/bin/catalina.sh start")
    except SubprocessError, error:
        LOGGER.error("Could not start Tomcat")
        LOGGER.error(error)
        raise

    check_tomcat_status()


def stop_tomcat():
    '''Stop tomcat server'''
    try:
        tomcat_pid = open("/usr/local/tomcat/logs/catalina.pid", "r").read()
    except IOError:
        print "PID file not found.  Tomcat not running"
        return
    if psutil.pid_exists(int(tomcat_pid)):
        try:
            esg_functions.stream_subprocess_output("/usr/local/tomcat/bin/catalina.sh stop")
        except SubprocessError, error:
            LOGGER.exception(error)
            LOGGER.error("Stopping Tomcat with catalina.sh script failed. Attempting to kill process...")
            try:
                os.kill(int(tomcat_pid), signal.SIGKILL)
            except OSError:
                print "Could not kill Tomcat process"
                raise

    check_tomcat_status()


def restart_tomcat():
    '''Restart tomcat server'''
    print "\n*******************************"
    print "Restarting Tomcat"
    print "******************************* \n"
    stop_tomcat()
    print "Sleeping for 7 seconds to allow shutdown"
    sleep(7)
    start_tomcat()
    print "Sleeping for 25 seconds to allow Tomcat restart"
    sleep(25)


def check_tomcat_status():
    '''Check status of tomcat server'''
    try:
        tomcat_pid = open("/usr/local/tomcat/logs/catalina.pid", "r").read()
        if psutil.pid_exists(int(tomcat_pid)):
            print "Tomcat is running"
            return tomcat_pid
        else:
            print "Tomcat stopped."
            return False
    except IOError:
        print "PID file not found.  Tomcat not running"


def run_tomcat_config_test():
    '''Run tomcat config test'''
    esg_functions.stream_subprocess_output("/usr/local/tomcat/bin/catalina.sh configtest")


def copy_credential_files(tomcat_install_config_dir):
    '''Copy Tomcat config files'''
    LOGGER.debug("Moving credential files into node's tomcat configuration dir: %s",
                 CONFIG["tomcat_conf_dir"])
    tomcat_credential_files = [CONFIG["truststore_file"], CONFIG["keystore_file"], CONFIG["tomcat_users_file"],
                               os.path.join(tomcat_install_config_dir, "hostkey.pem")]

    for file_path in tomcat_credential_files:
        credential_file_name = pybash.trim_string_from_head(file_path)
        if os.path.exists(os.path.join(tomcat_install_config_dir, credential_file_name)) and not os.path.exists(file_path):
            try:
                shutil.move(os.path.join(tomcat_install_config_dir,
                                         credential_file_name), file_path)
            except OSError:
                LOGGER.exception("Could not move file %s", credential_file_name)

    esgf_host = esg_functions.get_esgf_host()
    if os.path.exists(os.path.join(tomcat_install_config_dir, esgf_host + "-esg-node.csr")) and not os.path.exists(os.path.join(CONFIG["tomcat_conf_dir"], esgf_host + "-esg-node.csr")):
        shutil.move(os.path.join(tomcat_install_config_dir, esgf_host + "-esg-node.csr"),
                    os.path.join(CONFIG["tomcat_conf_dir"], esgf_host + "-esg-node.csr"))

    if os.path.exists(os.path.join(tomcat_install_config_dir, esgf_host + "-esg-node.pem")) and not os.path.exists(os.path.join(CONFIG["tomcat_conf_dir"], esgf_host + "-esg-node.pem")):
        shutil.move(os.path.join(tomcat_install_config_dir, esgf_host + "-esg-node.pem"),
                    os.path.join(CONFIG["tomcat_conf_dir"], esgf_host + "-esg-node.pem"))

def move_tomcat_credentials_to_esgf():
    '''
    Move selected config files into esgf tomcat's config dir (certificate et al)
    Ex: /esg/config/tomcat
    -rw-r--r-- 1 tomcat tomcat 181779 Apr 22 19:44 esg-truststore.ts
    -r-------- 1 tomcat tomcat    887 Apr 22 19:32 hostkey.pem
    -rw-r--r-- 1 tomcat tomcat   1276 Apr 22 19:32 keystore-tomcat
    -rw-r--r-- 1 tomcat tomcat    590 Apr 22 19:32 pcmdi11.llnl.gov-esg-node.csr
    -rw-r--r-- 1 tomcat tomcat    733 Apr 22 19:32 pcmdi11.llnl.gov-esg-node.pem
    -rw-r--r-- 1 tomcat tomcat    295 Apr 22 19:42 tomcat-users.xml
    Only called when migration conditions are present.
    '''
    tomcat_install_config_dir = os.path.join(CONFIG["tomcat_install_dir"], "conf")

    if tomcat_install_config_dir != CONFIG["tomcat_conf_dir"]:
        if not os.path.exists(CONFIG["tomcat_conf_dir"]):
            pybash.mkdir_p(CONFIG["tomcat_conf_dir"])

        esg_functions.backup(tomcat_install_config_dir)

        copy_credential_files(tomcat_install_config_dir)

        os.chown(CONFIG["tomcat_conf_dir"], esg_functions.get_user_id(
            "tomcat"), esg_functions.get_group_id("tomcat"))

def write_tomcat_env():
    '''Write tomcat environment info to /etc/esg.env'''
    EnvWriter.export("CATALINA_HOME", CONFIG["tomcat_install_dir"])
    esg_property_manager.set_property("PATH_with_tomcat", os.environ["PATH"]+":/usr/local/tomcat/bin")

def write_tomcat_install_log():
    '''Write tomcat version to install manifest'''
    esg_functions.write_to_install_manifest("tomcat", CONFIG["tomcat_install_dir"], TOMCAT_VERSION)
    esg_property_manager.set_property("tomcat.install.dir", CONFIG["tomcat_install_dir"])
    esg_property_manager.set_property("esgf.http.port", "80")
    esg_property_manager.set_property("esgf.https.port", "443")

def setup_tomcat_logrotate():
    '''If there is no logrotate file ${tomcat_logrotate_file} then create one
    default is to cut files after 512M up to 20 times (10G of logs)
    No file older than year should be kept.'''
    if not os.path.exists("/usr/sbin/logrotate"):
        print "Not able to find logrotate here [/usr/sbin/logrotate]"
        return False

    log_rot_size = "512M"
    log_rot_num_files = "20"
    tomcat_logrotate_file = "/etc/logrotate.d/esgf_tomcat"

    if not os.path.exists("/usr/local/tomcat/logs"):
        print "Sorry, could not find tomcat log dir"
        return False

    if not os.path.exists(tomcat_logrotate_file):
        print "Installing tomcat log rotation... [{}]".format(tomcat_logrotate_file)
        with open(tomcat_logrotate_file, "w") as logrotate_file:
            logrotate_file.write('"/usr/local/tomcat/logs/catalina.out" /usr/local/tomcat/logs/catalina.err {\n')
            logrotate_file.write('copytruncate\n')
            logrotate_file.write('size {log_rot_size}\n'.format(log_rot_size=log_rot_size))
            logrotate_file.write('rotate {log_rot_num_files}\n'.format(log_rot_num_files=log_rot_num_files))
            logrotate_file.write('maxage 365\n')
            logrotate_file.write('compress\n')
            logrotate_file.write('missingok\n')
            logrotate_file.write('create 0644 tomcat tomcat\n')

        os.chmod(tomcat_logrotate_file, 0644)

    tomcat_user = esg_functions.get_user_id("tomcat")
    tomcat_group = esg_functions.get_group_id("tomcat")

    if not os.path.exists("/usr/local/tomcat/logs/catalina.out"):
        print "Creating /usr/local/tomcat/logs/catalina.out"
        pybash.touch("/usr/local/tomcat/logs/catalina.out")
        os.chmod("/usr/local/tomcat/logs/catalina.out", 0644)
        os.chown("/usr/local/tomcat/logs/catalina.out", tomcat_user, tomcat_group)


    if not os.path.exists("/usr/local/tomcat/logs/catalina.err"):
        print "Creating /usr/local/tomcat/logs/catalina.err"
        pybash.touch("/usr/local/tomcat/logs/catalina.err")
        os.chmod("/usr/local/tomcat/logs/catalina.err", 0644)
        os.chown("/usr/local/tomcat/logs/catalina.err", tomcat_user, tomcat_group)

    if not os.path.exists("/etc/cron.daily/logrotate"):
        print "WARNING: Not able to find script [/etc/cron.daily/logrotate]"
        return False


def configure_tomcat():
    '''Configure tomcat for ESGF Node Manager'''
    print "*******************************"
    print "Configuring Tomcat... (for Node Manager)"
    print "*******************************"

    setup_tomcat_logrotate()
    esg_property_manager.set_property(
        "short.lived.certificate.server",
        esg_functions.get_esgf_host()
    )
    with pybash.pushd("/usr/local/tomcat/conf"):
        server_tmpl = os.path.join(CURRENT_DIRECTORY, "tomcat_conf/server.xml.tmpl")
        with open(server_tmpl, "r") as template:
            server_tmpl = template.read()
            server_xml = server_tmpl.format(
                proxyName=esg_functions.get_esgf_host(),
                tspass="changeit",
                kspass=esg_functions.get_java_keystore_password()
            )
        with open("/usr/local/tomcat/conf/server.xml", "w") as xml_file:
            xml_file.write(server_xml)
        tomcat_user = esg_functions.get_user_id("tomcat")
        tomcat_group = esg_functions.get_group_id("tomcat")
        os.chmod("/usr/local/tomcat/conf/server.xml", 0600)
        os.chown("/usr/local/tomcat/conf/server.xml", tomcat_user, tomcat_group)

        #Find or create keystore file
        if os.path.exists(CONFIG["keystore_file"]):
            print "Found existing keystore file {}".format(CONFIG["keystore_file"])
        else:
            print "creating keystore... "
            #create a keystore with a self-signed cert
            distinguished_name = "CN={esgf_host}".format(esgf_host=esg_functions.get_esgf_host())

            #if previous keystore is found; backup
            esg_keystore_manager.backup_previous_keystore(CONFIG["keystore_file"])

            #-------------
            #Make empty keystore...
            #-------------
            keystore_password = esg_functions.get_java_keystore_password()
            esg_keystore_manager.create_empty_java_keystore(CONFIG["keystore_file"], CONFIG["keystore_alias"], keystore_password, distinguished_name)


            #Setup temp CA
            CA.setup_temp_ca()

            #Fetch truststore to $tomcat_conf_dir
            if not os.path.exists(CONFIG["truststore_file"]):
                remote = "{}/certs/{}".format(
                    esg_property_manager.get_property("esg.root.url"),
                    os.path.basename(CONFIG["truststore_file"])
                )
                esg_functions.download_update(CONFIG["truststore_file"], remote)

            esg_truststore_manager.add_my_cert_to_truststore()

            esg_functions.change_ownership_recursive(CONFIG["tomcat_install_dir"], tomcat_user, tomcat_group)
            esg_functions.change_ownership_recursive(CONFIG["tomcat_conf_dir"], tomcat_user, tomcat_group)



def main():
    '''Main function'''
    print "\n*******************************"
    print "Setting up Tomcat {TOMCAT_VERSION}".format(TOMCAT_VERSION=TOMCAT_VERSION)
    print "******************************* \n"
    if download_tomcat():
        create_tomcat_user()
        extract_tomcat_tarball()
        os.environ["CATALINA_PID"] = "/tmp/catalina.pid"
        copy_config_files()
        configure_tomcat()
        remove_example_webapps()
        move_tomcat_credentials_to_esgf()
        write_tomcat_install_log()


if __name__ == '__main__':
    main()
