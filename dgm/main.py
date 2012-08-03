from argparse import ArgumentParser
import ConfigParser,os,shutil

dgm_version="0.1"
    
def _init(dgm):
    """Create .dgm under user home directory. Also initial .dgm/config file """
    """TODO:
        if home already exist, need to know if it is git-init, 
        if home path already has other files, should warning...
    """
    
    conf_dir = os.path.expanduser("~/.dgm")
    if not os.path.exists(conf_dir):
        os.makedirs(conf_dir, 0700)
        
    conf = os.path.join(conf_dir, 'config')
    if os.path.exists(conf):
        print ("dgm config is existed, it may be already initialised.")
        exit(0)
    
    if dgm.args.l:
        home_path = dgm.args.l
    else:
        home_path = os.getcwd()
        
    if home_path.startswith("~"):
        home_path = os.path.expanduser(home_path)
        
    if not os.path.exists(home_path):
        os.makedirs(home_path, 0700)
        
    if not os.path.isdir(home_path):
        print ("Home directory is not valid directory")
        exit(1)
    
    #Mkdir for this server
    server_path = os.path.join(home_path, dgm.args.s)
    if not os.path.exists(server_path):
        os.mkdir(server_path)
    
    #Also mkdir default metadata directory
    meta_path = os.path.join(home_path, "__metadata")
    if not os.path.exists(meta_path):
        os.mkdir(meta_path)
    
    
    #init git
    dgm.home_path = home_path
    _run_cmd_from_home(dgm, "git init")
    
    if dgm.args.r:
        _run_cmd_from_home(dgm, "git remote add origin %s" % dgm.args.r)
        
    confParser = ConfigParser.ConfigParser()
    confParser.add_section("config")
    confParser.set("config", "server_name", dgm.args.s)
    confParser.set("config", "home_path", home_path)
    confParser.set("config", "git_url", dgm.args.r)
    
    conf_file = open(conf, 'w')
    confParser.write(conf_file)
    conf_file.close()
    
    print("Initialise dgm repository successfully.")
    
def _add(dgm):
    """Copy file with original path to server path under current local repository . """
    files = dgm.args.filename
    
    for src_file in files:
        if not src_file.startswith(os.sep):
            src_file = os.path.join(os.getcwd(), src_file)
            
        if not os.path.exists(src_file):
            print("File %s does not exist" % src_file)
            exit(1)
        
        if os.path.isfile(src_file):
            #test if target path(home + current file absolute path) exist, if not, make it.
            src_file_path = os.path.dirname(src_file)
            src_file_name = os.path.basename(src_file)
            
            tgt_file_path = os.path.join(dgm.server_path, src_file_path.lstrip(os.sep))
            if not os.path.exists(tgt_file_path):
                os.makedirs(tgt_file_path, 0700)
                
            tgt_file = os.path.join(tgt_file_path, src_file_name)
            shutil.copy(src_file, tgt_file)
            
            _run_cmd_from_home(dgm, "git add %s" % tgt_file)
            print("File %s was added to repository" % src_file)
        

def _commit(dgm):
    """ Commit change to local git repository """
    _run_cmd_from_home(dgm, "git commit -m'%s'" % dgm.args.m)
    
def _status(dgm):
    """ Retrieve local repository status"""
    _run_cmd_from_home(dgm, "git status")

def _push(dgm):
    """ Push local repository master to remote """
    if dgm.git_url:
        _run_cmd_from_home(dgm, "git push origin master")
    else:
        print "No valid remote git URL set. Run [dgm remote -r {gitURL}] first"
        exit(1)

def _remote(dgm):
    """ Add remote repository as origin """
    _run_cmd_from_home(dgm, "git remote add origin %s", dgm.args.r)


def main():
    dgm = DGM()
    
    if dgm.args.command == 'init':
        _init(dgm)
    elif dgm.args.command == 'add':
        _add(dgm)
    elif dgm.args.command == 'status':
        _status(dgm)
    elif dgm.args.command == 'commit':
        _commit(dgm)
    elif dgm.args.command == 'push':
        _push(dgm)
    elif dgm.args.command == 'remote':
        _remote(dgm)
    elif dgm.args.command == 'print':
        print ("======================================================")
        print ("Server name: [%s]" % dgm.server_name)
        print ("Home directory: [%s]" % dgm.home_path)
        print ("Home for server directory: [%s]" % dgm.server_path)
        print ("Git URL: [%s]" % dgm.git_url)
        print ("======================================================")
        

def _run_cmd_from_home(dgm, cmd):
    pwd = os.getcwd()
    os.chdir(dgm.home_path)
    os.system(cmd)
    os.chdir(pwd)
    
        
class DGM:
    def __init__(self):
        
        #Read input args
        parser = ArgumentParser(prog='dgm', description='Distribute file git management.')
        subparsers = parser.add_subparsers(dest='command', help='Command help')
        
        #Init
        cmd_init_parser = subparsers.add_parser("init", help="Init local repository")
        cmd_init_parser.add_argument("-s", help="server name", required=True)
        cmd_init_parser.add_argument("-l", help="home directory - absolute path or start with tilde. If not preset, using current directory.")
        cmd_init_parser.add_argument("-r", help="remote git url")
        
        #Add
        cmd_add_parser = subparsers.add_parser("add", help="Add file to local repository")
        cmd_add_parser.add_argument("filename", nargs='+')
        
        #Commit
        cmd_commit_parser = subparsers.add_parser("commit", help="commit file to local repository")
        cmd_commit_parser.add_argument('-m', help='comment', required=True)
        
        #Status
        subparsers.add_parser("status", help="Check status of local repository")
        
        #Push
        subparsers.add_parser("push", help="Push local repository master to remote")
        
        
        #remote
        cmd_commit_parser = subparsers.add_parser("remote", help="Remote git management ")
        cmd_commit_parser.add_argument('-r', help='Remote git URL', required=True)
        
        #Print configuration
        subparsers.add_parser("print", help="Print configuration options")
        
        self.args = parser.parse_args()
        
        #Read config
        conf_file = os.path.join(os.path.expanduser("~/.dgm"), 'config')
        if os.path.exists(conf_file) and os.path.isfile(conf_file):
            confParser = ConfigParser.ConfigParser()
            confParser.read(conf_file)
            self.server_name = confParser.get('config', 'server_name');
            self.home_path = confParser.get('config', 'home_path')
            try:
                self.git_url = confParser.get('config', 'git_url')
            except ConfigParser.NoOptionError:
                self.git_url = None
            
            #other variables
            self.meta_path = os.path.join(self.home_path, "__metadata")
            self.server_path = os.path.join(self.home_path, self.server_name)
        else:
            if self.args.command != 'init':
                print "Run init command first"

    
if __name__ == "__main__":
    main()