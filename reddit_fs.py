#!/usr/bin/env pythonOA

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
        self.comment_files = ["no comments", "content", "newcomment"]
        #self.post_files = ["no comments", "content", "newpost"]
        self.seen_submissions = {}
        print "ready"

    # Filesystem methods
    # ==================
            
    def access(self, path, mode):
        print "EVALUATED AS", self.path_to_object(path)
        if self.path_to_object(path) is None:
            raise FuseOSError(errno.ENOENT)
        #return 0
        #pass
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

    def is_subreddit(self, name):
        for sub in self.subreddits:
            if sub.display_name == name:
                return True
        return False

    def fname_to_id(self, fname):
        """
        Extracts the post/comment id portion from a directory name.
        """
        return fname[75:]
    
    def post_to_fname(self, post):
        """
        Converts a post to a string containing some of the title of the post
        and the id of the post.
        """
        fname = post.title[:74] + " " + post.id
        fname = fname.replace("/", "|")
        return fname.replace("\n", " ")

    def comment_to_fname(self, comment):
        """
        Converts a comment to a string containing some of the body of the
        comment and the id of the comment.
        """
        fname = comment.body[:74] + " " + comment.id
        fname = fname.replace("/", "|")
        return fname.replace("\n", " ")
        
    def getattr(self, path, fh=None):
        path_pieces = path.split("/")
        path_pieces = filter(lambda x: len(x) > 0, path_pieces)
        if len(path_pieces) == 0:
            return { 'st_mode': stat.S_IFDIR,
                     'st_size': 50}
        # need to add checks for different levels of the directory tree too
        else:
            if len(path_pieces) == 1 and self.is_subreddit(path_pieces[0]):
                return { 'st_mode': stat.S_IFDIR,
                         'st_size': 50}
            else:
                return { 'st_mode': stat.S_IFDIR,
                         'st_size': 50}

        #full_path = self._full_path(path)
        #st = os.lstat(full_path)
        #return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime','st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))

    def get_posts(self, subreddit, sort_key, num_posts=20):
        """
        Takes in a subreddit object, a string sort key and an optional number n
        posts to retrieve and retrieves the n posts from the given subreddit
        under the given sort key.
        """
        if sort_key == "hot":
            posts = subreddit.get_hot(limit=num_posts)
        elif sort_key == "new":
            posts = subreddit.get_new(limit=num_posts)
        elif sort_key == "rising": 
            posts = subreddit.get_rising(limit=num_posts)
        elif sort_key == "controversial": 
            posts = subreddit.get_controversial(limit=num_posts)
        elif sort_key == "top": 
            posts = subreddit.get_top(limit=num_posts)
        else:
            raise FuseOSError(errno.ENOENT)
        return posts

    def get_all_comments(self, comments):
        """
        Takes in a list of comments and gives back the list, replacing any
        MoreComments objects with their actual comments.
        """
        all_comments = []
        for comment in comments:
            if type(comment) == praw.objects.MoreComments and comment.count > 0:
                print "GOING DOWN", comment.comments()
                all_comments.extend(self.get_all_comments(comment.comments()))
            else:
                all_comments.append(comment)
        return all_comments 

    def find_comment(self, comments, comment_id):
        """
        Given a list of comments and a comment id to look for, returns the
        comment object if it can find it and none if it cannot. This function
        searches all comment objects that are not "MoreComments" objects first,
        reducing the expected number of praw calls to be made.
        """
        more_comments = []
        for comment in comments:
            if type(comment) == praw.objects.MoreComments and comment.count > 0:
                more_comments.append(comment)
            elif comment.id == comment_id:
                return comment
        for more_comment in more_comments:
            print "RECURSING"
            result = find_comment(more_comment.comments(), comment_id)
            if not result is None:
                return result
        return None
                                
    def path_to_object(self, path):
        """
        Given a path, returns either a tuple with a string describing the
        object found as well as the object representing the end of the path or
        returns None if that object does not exist (meaning an invalid path).
        """
        path_pieces = path.split("/")
        path_pieces = filter(lambda x: len(x) > 0, path_pieces) 
        if len(path_pieces) == 0:
            return "root", None

        # check if the subreddit part of the path exists
        subreddit_obj = None
        for sub in self.subreddits:
            if sub.display_name == path_pieces[0]:
                subreddit_obj = sub
                break
        if len(path_pieces) == 1 and not subreddit_obj is None:
            return "subreddit", subreddit_obj
        if subreddit_obj is None:
            return None

        # check if the sort key part of the path exists
        sort_key = None
        if path_pieces[1] in self.sort_keywords:
            sort_key = path_pieces[1]
        if len(path_pieces) == 2 and not sort_key is None:
            return "sort key", sort_key
        if sort_key is None:
            return None

        # check if the post part of the path exists
        post_obj = None
        posts = self.get_posts(subreddit_obj, sort_key)
        for post in posts:
            if path_pieces[2] == self.post_to_fname(post):
                post_obj = post
                break
        if len(path_pieces) == 3 and not post_obj is None:
            return "post", post_obj
        if post_obj is None:
            return None

        # check if our path has a special comment file
        if len(path_pieces) == 4 and path_pieces[3] in self.comment_files:
            return "comment file", None
        
        # check if the first comment part of the path exists
        comment_id = self.fname_to_id(path_pieces[3])
        comment_obj = self.find_comment(post_obj.comments, comment_id)
        if len(path_pieces) == 4 and not comment_obj is None:
            return "comment", comment_obj
        if comment_obj is None:
            return None

        # check if the rest of the comment parts of the path exist
        lower_comment_obj = None
        for i in range(4, len(path_pieces)):
            if len(path_pieces) == i + 1 and path_pieces[i] in self.comment_files:
                return "comment file", None
            comment_id = self.fname_to_id(path_pieces[i])
            lower_comment_obj = self.find_comment(comment_obj.replies, comment_id)
            if lower_comment_obj is None:
                return None
            comment_obj = lower_comment_obj
            lower_comment_obj = None

        if not comment_obj is None:
            return "comment", comment_obj

        return None
            
    def readdir(self, path, fh):
        """
        Ideas: add a /new, /top, etc. to the end of the path if the path is just
        a single subreddit (eg. /AskReddit/new)
        Default to what? (new maybe?)
        """
        #dirents = ['.', '..']
        yield "."
        yield ".."
        path_obj = self.path_to_object(path)
        if path_obj is None:
            raise OSError(errno.ENOENT)

        if path_obj[0] == "root":
            for s in self.subreddits:
                #dirents.append(s.display_name)
                yield s.display_name
        
        elif path_obj[0] == "subreddit":
            [(yield key) for key in self.sort_keywords]
            #dirents.extend(self.sort_keywords)
            #dirents.append("newpost")

        elif path_obj[0] == "sort key":
            path_pieces = path.split("/")
            path_pieces = filter(lambda x: len(x) > 0, path_pieces) 
            posts = self.get_posts(self.r.get_subreddit(path_pieces[0]), path_obj[1])
            for post in posts:
                #dirents.append(self.post_to_fname(post))
                yield self.post_to_fname(post)
        elif path_obj[0] == "post" or path_obj[0] == "comment":
            if path_obj[0] == "post":
                if self.post_to_fname(path_obj[1]) in self.seen_submissions:
                    comments = self.seen_submissions[self.post_to_fname(path_obj[1])]
                else:
                    comments = self.get_all_comments(path_obj[1].comments)
                    self.seen_submissions[self.post_to_fname(path_obj[1])] = comments
            else:
                comments = self.get_all_comments(path_obj[1].replies)
            for comment in comments:
                #dirents.append(self.comment_to_fname(comment))
                yield self.comment_to_fname(comment)
            print "COMMENTS LENGTH", len(comments), comments
            if len(comments) == 0:
                yield "no comments"
        # path_obj[0] must be "special file"
        else:
            pass
        #for r in dirents:
        #    yield r
            
        """path_pieces = path.split("/")
        # when you split "/", you get two empty strings. filter will fix this.
        path_pieces = filter(lambda x: len(x) > 0, path_pieces) 
        # show all subreddits (default or personal) if given path is the root.
        if len(path_pieces) == 0:
            for s in self.subreddits:
                dirents.append(s.display_name) 
        else:
            # go one level deep - show 'new', 'rising', etc.
            if len(path_pieces) == 1: 
                dirents.extend(self.sort_keywords)
                dirents.append("newpost")
            else:
                present = False # boolean to check if comments/posts are present
                sort_key = path_pieces[1] 
                posts = self.get_posts(path_pieces[0], sort_key)
                if len(path_pieces) == 2:
                    for post in posts:
                        dirents.append(self.post_to_fname(post))
                    
                elif len(path_pieces) > 2:
                    # walk through the all the posts and see if the path exists
                    for post in posts:
                        if self.post_to_fname(post) == path_pieces[2]:
                            comments = post.comments
                            present = True
                    if not present:
                        raise OSError(errno.ENOENT)
                    
                    for i in range(3, len(path_pieces)):
                        for comment in comments:
                            if self.post_to_fname(post) == path_pieces[i]:
                                # if it exists, grab the comments
                                comments = comment.comments 
                                present = True
                        # if you walk an invalid/old path name, then hit the error
                        if not present: 
                            raise OSError(errno.ENOENT)
                        present = False
                    
                    # finished walking through the path
                    for comment in comments:
                        dirents.append(self.comment_to_fname(comment))
               # else:
               #     for post in posts:
               #         if self
            #full_path = self._full_path(path)

            #if os.path.isdir(full_path):
            #    dirents.extend(os.listdir(full_path))
        """


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
    r = praw.Reddit(user_agent, cache_timeout=60, api_request_delay=1.0)
    if len(sys.argv) > 2:
        r.login(username=sys.argv[2], disable_warning=True)
        logged_in = True

    FUSE(RedditFS(r, logged_in), mountpoint, nothreads=True, foreground=True, debug=True)
    
