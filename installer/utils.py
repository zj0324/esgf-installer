import os
import errno
from string import Formatter

def check_populatable(name, template, keys):
    fieldnames = [fname for _, fname, _, _ in Formatter().parse(template) if fname]
    if name in fieldnames:
        raise Exception #TODO make a real exception for recursive templating
    for field in fieldnames:
        if field not in keys:
            raise Exception #TODO make a real exception for unsupported template keywords

def populated(template):
    fieldnames = [fname for _, fname, _, _ in Formatter().parse(template) if fname]
    if fieldnames:
        return False
    return True

def populate(template, values):
    fieldnames = [fname for _, fname, _, _ in Formatter().parse(template) if fname]
    if not fieldnames:
        return template
    replacements = {}
    for field in fieldnames:
        if field in values:
            replacements[field] = values[field]
        else:
            return template

    return template.format(**replacements)


def mkdir_p(path, mode=0777):
    ''' Creates the directory and any subdirectories listed in path '''
    try:
        os.makedirs(path, mode)
    except OSError as exc:
        if exc.errno != errno.EEXIST or not os.path.isdir(path):
            raise

def chown_R(fd, uid=-1, gid=-1):
    if os.path.isfile(fd):
        os.chown(fd, uid, gid)
    elif os.path.isdir(fd):
        for root, dirs, files in os.walk(os.path.realpath(fd)):
            for directory in dirs:
                os.chown(os.path.join(root, directory), uid, gid)
            for name in files:
                file_path = os.path.join(root, name)
                os.chown(file_path, uid, gid)