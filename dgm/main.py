from argparse import ArgumentParser
from datetime import datetime

import ConfigParser
import hashlib
import os
import shutil
import sys
import json

dgm_version="0.2"

def _init(dgm):
    """Create .dgm under user home directory. Also initial .dgm/config file """
    """TODO:
        if home already exist, need to know if it is git-init, 
        if home path already has other files, should warning...
    """
    
    conf_dir = os.path.expanduser("~/.dgm")
    if not os.path.exists(conf_dir):
        os.makedirs(conf_dir, 0o700)
        
    conf = os.path.join(conf_dir, 'config')
    if os.path.exists(conf):
        _stdout_error("DGM config is existed, it may be already initialised.")
        exit(0)
    
    if dgm.args.d:
        home_path = dgm.args.d
    else:
        home_path = os.getcwd()
        
    if home_path.startswith("~"):
        home_path = os.path.expanduser(home_path)
        
    if not os.path.exists(home_path):
        os.makedirs(home_path, 0o700)
        
    if not os.path.isdir(home_path):
        _stdout_error ("Home directory is not valid directory")
        exit(1)
    
    #Mkdir for this server
    server_path = os.path.join(home_path, dgm.args.n)
    if not os.path.exists(server_path):
        os.mkdir(server_path)
    
    #Also mkdir default metadata directory
    meta_path = os.path.join(home_path, "__metadata")
    if not os.path.exists(meta_path):
        os.mkdir(meta_path)
    
    
    #init git
    dgm.home_path = home_path
    _run_cmd_from_home(dgm, "git init")
    
    if dgm.args.s:
        _run_cmd_from_home(dgm, "git remote add origin %s" % dgm.args.s)
        
    confParser = ConfigParser.ConfigParser()
    confParser.add_section("config")
    confParser.set("config", "server_name", dgm.args.n)
    confParser.set("config", "home_path", home_path)
    confParser.set("config", "git_url", dgm.args.s)
    confParser.set("config", "group", dgm.args.g)
    confParser.set("config", "ignore_files", json.dumps(['.DS_Store']))

    conf_file = open(conf, 'w')
    confParser.write(conf_file)
    conf_file.close()
    
    _stdout_info("Initialise DGM repository successfully.")
    

def _monitor(dgm):
    """ Add directory to DGM - don't support recursive to child directories yet """
    for src_dir in dgm.args.dirname:
        src_dir = _canonical_file(src_dir)

        if src_dir not in dgm.monitored_directories:
            dgm.monitored_directories.append(src_dir)

            for fl in _list_dir_files(dgm, src_dir):
                _stdout(fl)

    _stdout_info(" ")
    _stdout_info(" ")

    input_str = raw_input("Do you want to add these files to DGM? (y|yes)")
    input_str = input_str.strip()

    if input_str.lower() == 'y' or input_str.lower() == 'yes':
        # checkin all files
        dgm.args.f = True  # focus update
        dgm.args.ic = False  # auto commit
        for src_dir in dgm.args.dirname:
            _checkin_dir(dgm, src_dir)

        # update conf
        conf_file = os.path.join(os.path.expanduser("~/.dgm"), 'config')
        confParser = ConfigParser.ConfigParser()
        confParser.read(conf_file)
        confParser.set("config", 'monitored_directories', json.dumps(dgm.monitored_directories))
        with open(conf_file, 'w') as f:
            confParser.write(f)


def _add(dgm):
    """Copy file with original path to server path under current local repository . """
    
    files = dgm.args.filename
    ret_code = 0
    for src_file in files:
        src_file = _canonical_file(src_file)
            
        if not os.path.exists(src_file):
            _stdout_error("File %s does not exist" % src_file)
            ret_code = 1
            continue
        
        if os.path.isfile(src_file):
            #test if target path(home + current file absolute path) exist, if not, make it.
            src_file_path = os.path.dirname(src_file)
            src_file_name = os.path.basename(src_file)
            
            tgt_file_path = _clone_dirs(dgm.server_path, src_file_path)
                
            tgt_file = os.path.join(tgt_file_path, src_file_name)
            if os.path.exists(tgt_file):
                _stdout_error("%s is already in DGM, run <dgm checkin> to check in file update." % src_file)
                ret_code = 1
                continue
            
            _copy(src_file, tgt_file)
            
            _run_cmd_from_home(dgm, "git add %s" % tgt_file)
            _run_cmd_from_home(dgm, "git commit -m'Initial - %s'" % src_file)
                
            _stdout_info("%s is added to DGM repository" % src_file)
        else:
            _stdout_error("%s is directory, Using `dgm monitor` instead." % src_file)    
            ret_code = 1        

    exit(ret_code)

def _remove(dgm):
    """Remove file form  local DGM repository . """
    
    files = dgm.args.filename
    ret_code = 0
    for src_file in files:
        src_file = _canonical_file(src_file)
            
        #test if target path(home + current file absolute path) exist, if not, make it.
        src_file_path = os.path.dirname(src_file)
        src_file_name = os.path.basename(src_file)
        
        tgt_file_path = os.path.join(dgm.server_path, src_file_path.lstrip(os.sep))
        tgt_file = os.path.join(tgt_file_path, src_file_name)
        
        if not os.path.exists(tgt_file):
            _stdout_error("%s does not exist in DGM." % src_file)
            ret_code = 1
            continue
        
        if os.path.isfile(tgt_file):
            os.remove(tgt_file)
            
            _run_cmd_from_home(dgm, "git rm %s" % tgt_file)
                
            _stdout_info("%s is removed DGM repository" % src_file)
        else:
            _stdout_error("%s is directory, only files are accepted." % src_file)    
            ret_code = 1        

    exit(ret_code)
    
def _apply(dgm):
    """Copy DGM file to overwrite source file"""
    
    force = dgm.args.f
    is_all_files = _is_allfiles(dgm.args.filename)
    ret_code = 0
    
    dirty = False
    for dgm_file, src_file in _processed_files(dgm):
            
        if not os.path.exists(dgm_file):
            _stdout_error("File %s does not exist in DGM repository" % src_file)
            ret_code = 1
            continue

        if os.path.isfile(dgm_file):
            src_file_path = os.path.dirname(src_file)
            if not os.path.exists(src_file_path):
                #For safe reason, don't create source directory
                _stdout_error("Directory %s does not exist, please create manually" % src_file_path)
                ret_code = 1
                continue
            
            overwrite = not os.path.exists(src_file)
            if not overwrite:
                # Source file exist, check if it is older than DGM copy
                if _compare_file_mtime(dgm_file, src_file) > 0:
                    overwrite = True
                elif _compare_file_mtime(dgm_file, src_file) == 0:
                    #if unmodified file, only parameter has explicit filename with force flag, then update.  
                    if force and not is_all_files: 
                        overwrite = True
                    elif not is_all_files:
                        #if without force flag and  explicit filename, we need tell user this file is not updated because it is unmodified.
                        _stdout_error("%s is same with DGM file. Try use -f option to force to apply." % src_file)
                        
                    #if it wildcard file, keep silent in same file - we never copy unmodified file whatever force or not.
                else:
                    if force:
                        overwrite = True
                    else:
                        #if not force, source file is also newer than DGM file, we need tell user, this is dangerous to overwrite local change.  
                        _stdout_error("%s has updated before last checkin. Try use -f option to force to apply." % src_file)
                        
                    
            if overwrite:
                _copy(dgm_file, src_file)
                _stdout_info("%s is applied." % src_file)
                dirty = True
            
        else:
            _stdout_error("DGM File %s is directory, only files are accepted." % dgm_file)
            ret_code = 1
            continue

    if not dirty:
        _stdout_info("No file is applied")
        
    exit(ret_code)

def _diff(dgm):
    """ Copy source files to DGM """
    
    for dgm_file, src_file in _processed_files(dgm):
        _stdout_info("diff %s " % src_file)
        _run_cmd_from_home(dgm, "diff  %s %s" % (dgm_file, src_file)) 


def _list_dir_files(dgm, src_dir):
    src_dir = _canonical_file(src_dir)
    dir_files = []
    src_files = os.listdir(src_dir)
    for fl in src_files:
        if fl in dgm.ignore_files:
            continue

        fl = os.path.join(src_dir, fl)
        if os.path.isfile(fl):
            dir_files.append(fl)
        else:
            dir_files.extend(_list_dir_files(dgm, fl))

    return dir_files


def _checkin_dir(dgm, src_dir):
    dgm.args.filename = _list_dir_files(dgm, src_dir)
    _checkin(dgm, auto_add=True)


def _checkin(dgm, auto_add=False):
    """ Copy source files to DGM """
    
    force = dgm.args.f
    is_all_files = _is_allfiles(dgm.args.filename)
    dirty = False
    ret_code = 0

    if is_all_files:
        for src_dir in dgm.monitored_directories:
            _checkin_dir(dgm, src_dir)

    for dgm_file, src_file in _processed_files(dgm):
        if not os.path.exists(src_file):
            continue

        if not os.path.isfile(src_file):
            _checkin_dir(dgm, src_file)
            continue

        if not auto_add and not os.path.exists(dgm_file):
            _stdout_error("%s does not in  in DGM yet, run <dgm add> to add this file first." % src_file)
            ret_code = 1
            continue

        if os.path.isfile(src_file):

            overwrite = not os.path.exists(dgm_file)
            if not overwrite:
                # DGM file exist, check if it is older than source
                if _compare_file_mtime(src_file, dgm_file) > 0:
                    overwrite = True
                elif not force and not is_all_files and not auto_add:
                    # if parameters is with real file names, then we need explicitly to tell user if the files are applied or not
                    if _compare_file_mtime(src_file, dgm_file) == 0:
                        _stdout_error("%s DGM file is same than source file. Try use -f option." % src_file)
                    else:
                        _stdout_error("%s DGM file is newer than source file. Try use -f option or apply first." % src_file)

            if force or overwrite:
                _copy(src_file, dgm_file)
                _run_cmd_from_home(dgm, "git add %s" % dgm_file)
                _stdout_info("%s is checked in." % dgm_file)
                dirty = True
        else:
            _stdout_error("Source file %s is directory - DGM can not process in directory level" % src_file)
            ret_code = 1
            continue

    if not dirty:
        _stdout_info("No file is checked in")
    else:
        if not dgm.args.ic:
            _run_cmd_from_home(dgm, "git commit -m'Auto commit at %s'" % datetime.now())

    exit(ret_code)

                
def _commit(dgm):
    """ Commit change to local git repository """
    _run_cmd_from_home(dgm, "git commit -m'%s'" % dgm.args.m)
    
def _status(dgm):
    """ Retrieve local repository status"""
    
    all_info = dgm.args.a
    
    count = 0
    status_files = _compare_files(dgm)

    files = status_files[FileStatus.dgm_newer]
    if files:
        _stdout ("DGM file is newer than source file:")
        _stdout ("    Use dgm apply <file> to copy them from DGM repository")
        _stdout ("  ")
        for dgm_file, src_file in files:
            _stdout_info ("+ %s" % src_file)
            count += 1
            
    files = status_files[FileStatus.src_newer]
    if files:
        _stdout ("Source file is newer than DGM file:")
        _stdout ("    Use dgm checkin <file> to put them into DGM repository")
        _stdout ("  ")
        for dgm_file, src_file in files:
            _stdout_info ("* %s" % src_file)
            count += 1

    if not all_info:    
        files = status_files[FileStatus.src_notfound]
        if files:
            _stdout_info("Note: %d source file%s doesn't exist in your local file system." % (len(files), 's' if len(files) > 1 else ''))

    if all_info:
        files = status_files[FileStatus.src_notfound]
        if files:
            _stdout_error("Source file missing:")
            _stdout_error("    Use dgm apply <file> to copy them from DGM repository")
            _stdout_error("  ")
            for dgm_file, src_file in files:
                _stdout_error("- %s" % src_file)
                count += 1

        files = status_files[FileStatus.same]
        _stdout ("Files are  identical in DGM and source:")
        _stdout ("  ")
        for dgm_file, src_file in files:
            _stdout_info ("= %s" % src_file)
            count += 1
        
        _stdout(" ")
        _stdout("Managed files: %i" % count)           
    else:
        if count == 0:
            _stdout_info("All DGM filesdg are synchronised.")
             
    _stdout(" ")                     
    _stdout(" ")                     
    _stdout("DGM repository git status")
    _run_cmd_from_home(dgm, "git status")

def _push(dgm):
    """ Push local repository master to remote """
    if dgm.git_url:
        _run_cmd_from_home(dgm, "git push origin master")
    else:
        _stdout_error("No valid remote git URL set. Run [dgm remote -r {gitURL}] first")
        exit(1)
        

def _pull(dgm):
    """ Pull remote to  local repository master """
    if dgm.git_url:
        _run_cmd_from_home(dgm, "git pull origin master")
        
        _clean_dgm(dgm)
    else:
        _stdout_error("No valid remote git URL set. Run [dgm remote -r {gitURL}] first")
        exit(1)

def _config(dgm):
    """ Add remote repository as origin """
    
    #TODO: add/remove remote URL, Server etc.
#    confParser = ConfigParser.ConfigParser()
#    confParser.set("config", "git_url", dgm.args.s)
#    
#    conf_dir = os.path.expanduser("~/.dgm")
#    conf = os.path.join(conf_dir, 'config')
#    conf_file = open(conf, 'w')
#    confParser.write(conf_file)
#    conf_file.close()
#    
#    _run_cmd_from_home(dgm, "git remote add origin %s" % dgm.args.s)
    
    _stdout(" ")   
    _stdout("Server configuration:")
    _stdout(" ")   
    _stdout_info ("Server name: [%s]" % dgm.server_name)
    _stdout_info ("Home directory: [%s]" % dgm.home_path)
    _stdout_info ("Home for server directory: [%s]" % dgm.server_path)
    _stdout_info ("Group: [%s]" % dgm.group)
    _stdout_info ("Git URL: [%s]" % dgm.git_url)
    

def main():
    dgm = DGM()
    
    if dgm.args.command == 'init':
        _init(dgm)
    elif dgm.args.command == 'add':
        _add(dgm)
    elif dgm.args.command == 'commit':
        _commit(dgm)
    elif dgm.args.command == 'push':
        _push(dgm)
    elif dgm.args.command == 'checkin':
        _checkin(dgm)
    elif dgm.args.command == 'config':
        _config(dgm)
    elif dgm.args.command == 'pull':
        _pull(dgm)
    elif dgm.args.command == 'apply':
        _apply(dgm)
    elif dgm.args.command == 'rm':
        _remove(dgm)
    elif dgm.args.command == 'diff':
        _diff(dgm)
    elif dgm.args.command == 'status':
        _status(dgm)
    elif dgm.args.command == 'monitor':
        _monitor(dgm)

def _processed_files(dgm):
    files = dgm.args.filename
    if _is_allfiles(files):
        #All files
        files =  [src_file for dgm_file, src_file in _retrieve_files(dgm)]

    for src_file in files:
        src_file = _canonical_file(src_file)

        src_file_path = os.path.dirname(src_file)
        src_file_name = os.path.basename(src_file)
        
        dgm_file_path = os.path.join(dgm.server_path, src_file_path.lstrip(os.sep))
        dgm_file = os.path.join(dgm_file_path, src_file_name)
        yield dgm_file, src_file


def _clean_dgm(dgm):
    """ Remove non-managed directory """
    
    #TODO: multiple server managed
    if dgm.group == '*':
        # all server
        _reset_gitignore(dgm)
    else:
        # only current server
        dirs = os.listdir(dgm.home_path)
        
        ignores = []
        for rdir in dirs:
            if os.path.isfile(os.path.join(dgm.home_path, rdir)): continue
            if ".git" == rdir: continue
            if "__metadata" == rdir: continue
            if dgm.server_name == rdir: continue
            
            #A little dangerous...
            #shutil.rmtree(os.path.join(dgm.home_path, rdir))
            ignores.append(rdir+os.path.sep+"*")
            
            _stdout_info("%s managed files is ignored..." % rdir)
        _reset_gitignore(dgm, ignores)
        
def _reset_gitignore(dgm, ignores = None):
    with open(os.path.join(dgm.home_path, ".gitignore"),'w+') as gitignore:
        #always ignore itself
        gitignore.write('.gitignore\n')
        if ignores:
            for ig in ignores:
                gitignore.write('%s\n' % ig)
        
        
        
        
def _compare_file_mtime(dgm_file, src_file):
    """ Compare file modified time - Note, if use shuil.copy2(), the modified time may not accurate to microseconds as OS limitation.
        Simply use os.path.getmtime() won't get correctly result. Here will compare mtime to seconds level.
        
        If return greater than 0, dgm_file > src_file
        If return less than 0, dgm_file < src_file
        If return equal 0, dgm_file == src_file
    """  
    
    delta = datetime.fromtimestamp(os.path.getmtime(dgm_file)) - datetime.fromtimestamp(os.path.getmtime(src_file))
    
    return int(delta.total_seconds())



def _canonical_file(src_file):
    if src_file.startswith("~/"):
        src_file = os.path.expanduser(src_file)
    
    return os.path.realpath(src_file) 

    
def _is_allfiles(files):
    return ( len(files) == 1 and files[0] == '.' )
                
def _compare_files(dgm):
    """ Check all files under dgm managed, if they are different, then overwrite filename in dgm side.  
        So, this means, dgm managed files are not suppose to updated which will be overwritten even it is newer than original one"""
    
    status_files = {FileStatus.src_notfound:[],FileStatus.same:[], FileStatus.dgm_newer:[], FileStatus.src_newer:[]}
    
    for dgm_file, src_file in _retrieve_files(dgm):
        if not os.path.exists(src_file):
            status_files.get(FileStatus.src_notfound).append((dgm_file,src_file))
        else:
            #To keep consistent with check_in() and apply(), don't do digest comparison 
#            dgm_digest = _file_digest(dgm_file)
#            src_digest = _file_digest(src_file)
#            if dgm_digest == src_digest:
#                status_files.get(FileStatus.same).append((dgm_file,src_file))
#            else:
            
            diff = _compare_file_mtime(dgm_file, src_file)
            if diff  > 0:
                status_files.get(FileStatus.dgm_newer).append((dgm_file,src_file))
            elif diff == 0:
                status_files.get(FileStatus.same).append((dgm_file,src_file))
            else:
                status_files.get(FileStatus.src_newer).append((dgm_file,src_file))
            
    return status_files

def _retrieve_files(dgm):
    for dirpath, dirnames, filenames in os.walk(dgm.server_path):
        for filename in filenames:
            dgm_file = os.path.join(dirpath,filename)
            
            #remove dgm root directory, then get its original file full path.
            src_file = _get_src_file(dgm, dgm_file)
            yield dgm_file, src_file
            
            
def  _file_digest(filename):
    digest = hashlib.md5()
    
    afile = open(filename,'r')
    blocksize = 1024*10
    buf = afile.read(blocksize)
    while len(buf) > 0:
        digest.update(buf)
        buf = afile.read(blocksize)
        
    afile.close()
    
    return digest.digest()

def _run_cmd_from_home(dgm, cmd):
    pwd = os.getcwd()
    os.chdir(dgm.home_path)
    os.system(cmd)
    os.chdir(pwd)
    
def _get_src_file(dgm, dgm_file):
    src_file = os.path.relpath(dgm_file, dgm.server_path)
    src_file = os.path.join(os.path.sep, src_file);
        
    return src_file

def _copy(src_file, tgt_file):
    #is possible or useful to keep owner/group information here?
    tgt_path = os.path.dirname(tgt_file)
    if not os.path.exists(tgt_path):
        os.makedirs(tgt_path)

    shutil.copy2(src_file, tgt_file)
    
def _clone_dirs(server_path, src_file_path):
    """ Get  DGM directories. If directory does not exist """
    
    tgt_file_path = os.path.join(server_path, src_file_path.lstrip(os.sep))
    if not os.path.exists(tgt_file_path):
        #create it with src_dir with same owner and permissions
        os.makedirs(tgt_file_path, 0o700)
        
    return tgt_file_path

  
def _stdout(string):
    print(string)
    
def _stdout_error(string):
    #red message
    print(_color_message(string, error=True))
    
def _stdout_info(string):
    #green message
    print(_color_message(string, error=False))
    
    
def _color_message(string, error=False, bold=False):
    if not sys.stdout.isatty():
        return string
    
    attr = []
    if error:
        # red
        attr.append('31')
    else:
        # green
        attr.append('32')
    if bold:
        attr.append('1')
    return '\x1b[%sm%s\x1b[0m' % (';'.join(attr), string)

class FileStatus:
    same, dgm_newer, src_newer, src_notfound = range(4)
        
class DGM:
    def __init__(self):
        
        #Read input args
        parser = ArgumentParser(prog='dgm', description='Distribute file git management.')
        subparsers = parser.add_subparsers(dest='command', help='Command help')
        
        #Init
        cmd_init_parser = subparsers.add_parser("init", help="Init local DGM repository")
        cmd_init_parser.add_argument("-n", help="Server name", required=True)
        cmd_init_parser.add_argument("-d", help="Home directory - absolute path or start with tilde. If not preset, using current directory.")
        cmd_init_parser.add_argument("-s", help="Remote git  server url")
        cmd_init_parser.add_argument("-g", help="Group of servers. If '*' means all servers")
        
        #Add
        cmd_add_parser = subparsers.add_parser("add", help="Add new files to local DGM repository")
        cmd_add_parser.add_argument("filename", nargs='+')
        
        cmd_monitor_parser = subparsers.add_parser("monitor", help="Add directory to local DGM repository")
        cmd_monitor_parser.add_argument("dirname", nargs='+')

        #diff
        cmd_diff_parser = subparsers.add_parser("diff", help="Diff files to local DGM repository")
        cmd_diff_parser.add_argument("filename", nargs='*', default='.')

        # Status
        cmd_status_parser = subparsers.add_parser("status", help="Display status of local DGM repository")
        cmd_status_parser.add_argument("-a", help="List all fields in DGM repository and configuration information.", required=False, action='store_const', const=True)

        #Checkin
        cmd_checkin_parser = subparsers.add_parser("checkin", help="Check in source files into local DGM repository and commit")
        cmd_checkin_parser.add_argument("-f", help="Force checkin local files to overwrite DGM files, even DGM file is newer than local file.", required=False, action='store_const', const=True)
        cmd_checkin_parser.add_argument("-ic", help="Only update DMG file without commit.", required=False, action='store_const', const=True)
        cmd_checkin_parser.add_argument("filename", nargs='+')
        
        #Commit
        cmd_commit_parser = subparsers.add_parser("commit", help="Git commit in local DGM repository")
        cmd_commit_parser.add_argument('-m', help='comment', required=True)
        
        #Push
        subparsers.add_parser("push", help="Push local DGM repository master to remote git")
        
        #Pull
        subparsers.add_parser("pull", help="Pull remote git to local DGM repository")
        
        #Apply
        cmd_apply_parser = subparsers.add_parser("apply", help="Copy source file from DGM local repository")
        cmd_apply_parser.add_argument("-f", help="Force overwrite local file from DGM, even local file is newer than DGM file.", required=False, action='store_const', const=True)
        cmd_apply_parser.add_argument("filename", nargs='+')
        
        #Remove 
        cmd_remove_parser = subparsers.add_parser("rm", help="Remove new files to local DGM repository")
        cmd_remove_parser.add_argument("filename", nargs='+')
        
        #Config
        cmd_config_parser = subparsers.add_parser("config", help="Config")
#        config_subparsers = cmd_config_parser.add_subparsers(dest='Config command', help='Config command help')
#        config_add_parser = config_subparsers.add_parser("add", help="Add config options")
#        config_add_parser.add_argument('-s', help='Add or remove git remote URL', required=False)

        
        self.args = parser.parse_args()
        
        #Read config
        conf_file = os.path.join(os.path.expanduser("~/.dgm"), 'config')
        if os.path.exists(conf_file) and os.path.isfile(conf_file):
            confParser = ConfigParser.ConfigParser()
            confParser.read(conf_file)
            self.server_name = confParser.get('config', 'server_name').strip()
            self.home_path = confParser.get('config', 'home_path').strip()
            try:
                self.git_url = confParser.get('config', 'git_url')
            except ConfigParser.NoOptionError:
                self.git_url = None
            
            self.group  = confParser.get('config', 'group')
            try:
                md = confParser.get('config', 'monitored_directories')
                self.monitored_directories = json.loads(md)
            except ConfigParser.NoOptionError:
                self.monitored_directories = []

            try:
                ig = confParser.get('config', 'ignore_files')
                self.ignore_files = json.loads(ig)
            except ConfigParser.NoOptionError:
                self.ignore_files = []

            #other variables
            self.meta_path = os.path.join(self.home_path, "__metadata")
            self.server_path = os.path.join(self.home_path, self.server_name)

        else:
            if self.args.command != 'init':
                _stdout_info("Run init command first")

    
if __name__ == "__main__":
    main()