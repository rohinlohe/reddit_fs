#!/usr/bin/env python

from __future__ import with_statement

import errno
import os
import praw
import random
import sys
import stat


from fuse import FUSE, FuseOSError, Operations


class RedditFS(Operations):
    def __init__(self, r, logged_in):
        self.logged_in = logged_in
        self.r = r
        if self.logged_in:
            subreddits = self.r.get_my_subreddits(limit=None)
        else:
            subreddits = self.r.default_subreddits(limit=None)
        self.subreddits = list(subreddits)
        self.sort_keywords = ["hot", "new", "rising", "controversial", "top"]
        print "ready"

    # Filesystem methods
    # ==================
            
    def access(self, path, mode):
        pass
        #full_path = self._full_path(path)
        #if not os.access(full_path, mode):
        #    raise FuseOSError(errno.EACCES)
        
    def chmod(self, path, mode):
        pass
        #full_path = self._full_path(path)
        #return os.chmod(full_path, mode)
        
    def chown(self, path, uid, gid):
        pass
        #full_path = self._full_path(path)
        #return os.chown(full_path, uid, gid)

    def getattr(self, path, fh=None):
        path_pieces = path.split("/")
        path_pieces = filter(lambda x: len(x) > 0, path_pieces)
        if len(path_pieces) == 0:
            return { 'st_mode': stat.S_IFDIR,
                     'st_size': 50}
        # need to add checks for different levels of the directory tree too
        else:
            return { 'st_mode': stat.S_IFDIR,
                     'st_size': 50}

        #full_path = self._full_path(path)
        #st = os.lstat(full_path)
        #return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime','st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))

    def get_posts(self, subreddit, sort_key, num_posts=20):
        subreddit_target = r.get_subreddit(subreddit)
        if sort_key == "hot":
            posts = subreddit_target.get_hot(limit=num_posts)
        elif sort_key == "new":
            posts = subreddit_target.get_new(limit=num_posts)
        elif sort_key == "rising": 
            posts = subreddit_target.get_rising(limit=num_posts)
        elif sort_key == "controversial": 
            posts = subreddit_target.get_controversial(limit=num_posts)
        elif sort_key == "top": 
            posts = subreddit_target.get_top(limit=num_posts)
        else:
            raise NameError("Invalid subreddit sort key")
        return posts

    def readdir(self, path, fh):
        """
        Ideas: add a /new, /top, etc. to the end of the path if the path is just
        a single subreddit (eg. /AskReddit/new)
        Default to what? (new maybe?)
        """
        dirents = ['.', '..']
        path_pieces = path.split("/")
        path_pieces = filter(lambda x: len(x) > 0, path_pieces)
        print "path pieces is", path_pieces
        if len(path_pieces) == 0:
            for s in self.subreddits:
                dirents.append(s.display_name)
        elif len(path_pieces) == 1 or len(path_pieces) == 2:
            sort_key = "new" if len(path_pieces) == 1 else path_pieces[1] 
            posts = self.get_posts(path_pieces[0], sort_key)
            for post in posts:
                dirents.append(post.title[:74] + " " + post.id)
            
        else:
            pass
            #full_path = self._full_path(path)

            #if os.path.isdir(full_path):
            #    dirents.extend(os.listdir(full_path))

        for r in dirents:
            yield r

    def readlink(self, path):
        pass
        #pathname = os.readlink(self._full_path(path))
        #if pathname.startswith("/"):
            # Path name is absolute, sanitize it.
        #    return os.path.relpath(pathname, self.root)
        #else:
        #    return pathname

    def mknod(self, path, mode, dev):
        pass
        #return os.mknod(self._full_path(path), mode, dev)

    def rmdir(self, path):
        pass
        #full_path = self._full_path(path)
        #return os.rmdir(full_path)

    def mkdir(self, path, mode):
        pass
        #return os.mkdir(self._full_path(path), mode)
    
    def statfs(self, path):
        #full_path = self._full_path(path)
        #stv = os.statvfs(full_path)
        return {'f_bavail': 20,
                'f_bfree': 20,
                'f_blocks': 40,
                'f_bsize': 2,
                'f_free': 20,
                'f_files': 40,
                'f_namemax': 80}
    #dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree','f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag','f_frsize', 'f_namemax'))

    def unlink(self, path):
        pass
        #return os.unlink(self._full_path(path))
    
    def symlink(self, name, target):
        pass
        #return os.symlink(name, self._full_path(target))
    
    def rename(self, old, new):
        pass
        #return os.rename(self._full_path(old), self._full_path(new))
    
    def link(self, target, name):
        pass
        #return os.link(self._full_path(target), self._full_path(name))
    
    def utimens(self, path, times=None):
        pass
        #return os.utime(self._full_path(path), times)
    
    # File methods
    # ============
    
    def open(self, path, flags):
        pass
        #full_path = self._full_path(path)
        #return os.open(full_path, flags)
    
    def create(self, path, mode, fi=None):
        pass
        #full_path = self._full_path(path)
        #return os.open(full_path, os.O_WRONLY | os.O_CREAT, mode)
    
    def read(self, path, length, offset, fh):
        pass
        #os.lseek(fh, offset, os.SEEK_SET)
        #return os.read(fh, length)
    
    def write(self, path, buf, offset, fh):
        pass
        #os.lseek(fh, offset, os.SEEK_SET)
        #return os.write(fh, buf)
    
    def truncate(self, path, length, fh=None):
        pass
        #full_path = self._full_path(path)
        #with open(full_path, 'r+') as f:
        #    f.truncate(length)
            
    def flush(self, path, fh):
        pass
        #return os.fsync(fh)

    def release(self, path, fh):
        pass
        #return os.close(fh)
    
    def fsync(self, path, fdatasync, fh):
        pass
        #return self.flush(path, fh)
    
        
if __name__ == '__main__':
    mountpoint = sys.argv[1]
    logged_in = False
    user_agent = "reddit_fs file system"
    r = praw.Reddit(user_agent)
    if len(sys.argv) > 2:
        r.login(username=sys.argv[2], disable_warning=True)
        logged_in = True

    FUSE(RedditFS(r, logged_in), mountpoint, nothreads=True, foreground=True, debug=True)
    
