#!/usr/bAin/env pythonOA

from __future__ import with_statement

import errno
import os
import praw
import random
import sys
import stat
import urllib2
import html2text

from utils import get_content_fnames, open_content
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
        self.content_extensions = ['.txt', '.html', '.gif', '.jpg', '.mp4', '.pdf', '.png']
        self.seen_submissions = {} # subreddit + sortkey -> [submissions]
        self.open_files = {} # fname -> file descriptor
        self.file_sizes = {} # fname -> file size
        self.content_fnames = {} # submission obj -> [fnames], extension
        self.max_content_files = 10 # maximum number of content files for one submission
        self.max_comments = 20 # maximum comment directories in a single directory
        self.file_size_threshold = 1000 # when checking size, also save file if below this size
        self.max_file_size = float('inf') # might wanna make this smaller (YouTube)
        print "ready"

    def comment_files(self):
        # python generator to give us all the possible content file names and
        # the other files we might find in a comment directory
        yield "no comments"
        yield "newcomment.txt"
        base = "content"
        for i in range(1, self.max_content_files):
            for ext in self.content_extensions:
                yield base + str(i) + ext

    # Filesystem methods
    # ==================
            
    def access(self, path, mode):
        if self.path_to_objects(path) is None:
            raise FuseOSError(errno.ENOENT)
        
    #def chmod(self, path, mode):
    #    pass
        #full_path = self._full_path(path)
        #return os.chmod(full_path, mode)
        
    #def chown(self, path, uid, gid):
    #    pass
        #full_path = self._full_path(path)
        #return os.chown(full_path, uid, gid)

    def post_fname_to_id(self, fname):
        """
        Extracts the post id portion from a directory name.
        """
        return fname[-6:]

    def comment_fname_to_id(self, fname):
        """
        Extracts the comment id portion from a directory name.
        """
        return fname[-7:]
    
    def post_to_fname(self, post):
        """
        Converts a post to a string containing some of the title of the post
        and the id of the post (post ids are 6 alpha-numeric characters).
        """
        fname = post.title[:74] + " " + post.id
        fname = fname.replace("/", "|")
        return fname.replace("\n", " ")

    def comment_to_fname(self, comment):
        """
        Converts a comment to a string containing some of the body of the
        comment and the id of the comment (comment ids are 7 alpha-numeric
        characters).
        """
        fname = comment.body[:73] + " " + comment.id
        fname = fname.replace("/", "|")
        return fname.replace("\n", " ")

    def get_content_fnames_wrap(self, obj, disp_fname):
        if obj in self.content_fnames:
            fnames, ext = self.content_fnames[obj]
        else:
            fnames, ext = get_content_fnames(obj, self.max_content_files)
            self.content_fnames[obj] = fnames, ext
        # get the content number (1 less than in the display name for purposes
        # of array indexing)
        if 'content' in disp_fname:
            content_num = int(disp_fname[len("content"):-4]) - 1
        else:
            content_num = 0
        # get the storage file that the display name maps to
        fname = fnames[content_num]
        return fname, content_num
        
    def getattr(self, path, fh=None):
        path_objs = self.path_to_objects(path)
        if path_objs is None:
            raise FuseOSError(errno.ENOENT)

        path_attrs = {}
        # root directory
        if len(path_objs) == 0:
            path_attrs['st_mode'] = stat.S_IFDIR
            path_attrs['st_size'] = len(self.subreddits)
            return path_attrs
        
        # if we are asking about a content file, look up the size
        if path_objs[-1] in self.comment_files():
            path_attrs['st_mode'] = stat.S_IFREG
            # get content file names and extensions
            fname, content_num = self.get_content_fnames_wrap(path_objs[-2], path_objs[-1])
            # if we have the info about this file cached, don't make another request                        
            if fname in self.file_sizes:
                path_attrs['st_size'] = self.file_sizes[fname]
            else:
                # look up the size and only download the full file if the size is small
                f, size = open_content(path_objs[-2], fname, content_num, self.file_size_threshold)
                if not f is None:
                    self.open_files[fname] = f
                self.file_sizes[fname] = size
                path_attrs['st_size'] = size

        else:
            path_attrs['st_mode'] = stat.S_IFDIR
            if type(path_objs[-1]) == praw.objects.Subreddit:
                path_attrs['st_size'] = 5
            elif path_objs[-1] in self.sort_keywords:
                path_attrs['st_size'] = 20
            elif type(path_objs[-1]) == praw.objects.Submission:
                path_attrs['st_size'] = path_objs[-1].num_comments
            elif type(path_objs[-1]) == praw.objects.Comment:
                # this will be too small if there are MoreComments objects
                path_attrs['st_size'] = len(path_objs[-1].replies)
        return path_attrs

    def get_posts(self, subreddit, sort_key, num_posts=20):
        """
        Takes in a subreddit object, a string sort key and an optional number n
        posts to retrieve and retrieves the n posts from the given subreddit
        under the given sort key.
        """
        submissions_name = subreddit.display_name + sort_key
        print "SUBMISSIONS_NAME IS", submissions_name
        if submissions_name in self.seen_submissions:
            return self.seen_submissions[submissions_name]
        elif sort_key == "hot":
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
        self.seen_submissions[submissions_name] = list(posts)
        return self.seen_submissions[submissions_name]

    def get_n_comments(self, comments, max_comments):
        """
        Takes in a list of comments and gives back the list, replacing any
        MoreComments objects with their actual comments.
        """
        all_comments = []
        more_comments = []
        for comment in comments:
            # don't give back too many comments!
            if (len(all_comments) >= max_comments):
                return all_comments
            # save the MoreComments objects for the end since they take awhile
            if type(comment) == praw.objects.MoreComments and comment.count > 0:
                more_comments.append(comment)
            else:
                all_comments.append(comment)
        for more_comment in more_comments:
            all_comments.extend(self.get_n_comments(more_comment.comments(),
                                max_comments - len(all_comments)))
        return all_comments 

    def find_comment(self, comments, comment_id):
        """
        Given a list of comments and a comment id to look for, returns the
        comment object if it can find it and none if it cannot. This function
        searches all comment objects that are not "MoreComments" objects first,
        reducing the expected number of praw calls to be made.
        """
        print "trying to find comment", comment_id
        if not comment_id.isalnum():
            return None
        more_comments = []
        for comment in comments:
            if type(comment) == praw.objects.MoreComments and comment.count > 0:
                more_comments.append(comment)
            elif comment.id == comment_id:
                return comment
        for more_comment in more_comments:
            result = self.find_comment(more_comment.comments(), comment_id)
            if not result is None:
                return result
        return None

                                
    def path_to_objects(self, path):
        """
        Given a path, returns either a tuple with a string describing the
        object found as well as the object representing the end of the path or
        returns None if that object does not exist (meaning an invalid path).
        """
        path_pieces = path.split("/")
        path_pieces = filter(lambda x: len(x) > 0, path_pieces)
        path_objs = []
        if len(path_pieces) == 0:
            return path_objs

        # check if the subreddit part of the path exists
        subreddit_obj = None
        for sub in self.subreddits:
            if sub.display_name == path_pieces[0]:
                subreddit_obj = sub
                break
        if subreddit_obj is None:
            return None

        path_objs.append(subreddit_obj)
        if len(path_pieces) == 1:
            return path_objs


        # check if the sort key part of the path exists
        sort_key = None
        if path_pieces[1] in self.sort_keywords:
            sort_key = path_pieces[1]
        if sort_key is None:
            return None
        path_objs.append(sort_key)
        if len(path_pieces) == 2:
            return path_objs
        
        if len(path_pieces) == 3 and path_pieces[2] == "newpost":
            return path_obj.append("newpost")

        # check if the post part of the path exists
        post_obj = None
        posts = self.get_posts(subreddit_obj, sort_key)
        for post in posts:
            if path_pieces[2] == self.post_to_fname(post):
                post_obj = post
                break
        if post_obj is None:
            return None
        path_objs.append(post_obj)
        if len(path_pieces) == 3:
            return path_objs
        

        # check if our path has a special comment file
        if len(path_pieces) == 4 and path_pieces[3] in self.comment_files():
            path_objs.append(path_pieces[3])
            return path_objs
        
        # check if the first comment part of the path exists
        comment_id = self.comment_fname_to_id(path_pieces[3])
        comment_obj = self.find_comment(post_obj.comments, comment_id)
        if comment_obj is None:
            return None
        path_objs.append(comment_obj)
        if len(path_pieces) == 4:
            return path_objs


        # check if the rest of the comment parts of the path exist
        lower_comment_obj = None
        for i in range(4, len(path_pieces)):
            print path_pieces[i]
            if len(path_pieces) == i + 1 and path_pieces[i] in self.comment_files():
                path_objs.append(path_pieces[i])
                return path_objs
            comment_id = self.comment_fname_to_id(path_pieces[i])
            lower_comment_obj = self.find_comment(comment_obj.replies, comment_id)
            if lower_comment_obj is None:
                return None
            path_objs.append(lower_comment_obj)
            comment_obj = lower_comment_obj
            lower_comment_obj = None

        if not comment_obj is None:
            return path_objs

        return None
            
    def readdir(self, path, fh):
        """
        Ideas: add a /new, /top, etc. to the end of the path if the path is just
        a single subreddit (eg. /AskReddit/new)
        Default to what? (new maybe?)
        """
        yield "."
        yield ".."
        path_objs = self.path_to_objects(path)
        if path_objs is None:
            raise FuseOSError(errno.ENOENT)

        # root directory
        if len(path_objs) == 0:
            for s in self.subreddits:
                yield s.display_name
            return
        path_type = type(path_objs[-1])

        # subreddit directory
        if len(path_objs) == 1:
            [(yield key) for key in self.sort_keywords]
            yield "newpost"

        # sortkey directory
        elif path_objs[-1] in self.sort_keywords:
            posts = self.get_posts(path_objs[0], path_objs[1])
            for post in posts:
                yield self.post_to_fname(post)

        # post or comment directory
        elif path_type == praw.objects.Submission or path_type == praw.objects.Comment:
            # check if we've looked up this object before
            if path_objs[-1] in self.content_fnames:
                content_files, ext = self.content_fnames[path_objs[-1]]
            # if we haven't, look it up and save it
            else:
                content_files, ext = get_content_fnames(path_objs[-1], self.max_content_files)
                self.content_fnames[path_objs[-1]] = content_files, ext
            for i in range(1, len(content_files) + 1):
                print "yielding", "content" + str(i) + ext
                yield "content" + str(i) + ext
            
            # get the comments (or replies to comments) and yield their directory names
            if path_type == praw.objects.Submission:
                comments = self.get_n_comments(path_objs[-1].comments, self.max_comments)
            else:
                comments = self.get_n_comments(path_objs[-1].replies, self.max_comments)
            for comment in comments:
                yield self.comment_to_fname(comment)
            # if there are no comments/replies, yield a no comments file
            if len(comments) == 0:
                yield "no comments"
        elif path_objs[-1] in self.comment_files():
            raise FuseOSError(errno.ENOTDIR)

    #def readlink(self, path):
    #    pass
        #pathname = os.readlink(self._full_path(path))
        #if pathname.startswith("/"):
            # Path name is absolute, sanitize it.
        #    return os.path.relpath(pathname, self.root)
        #else:
        #    return pathname

    #def mknod(self, path, mode, dev):
    #    pass
        #return os.mknod(self._full_path(path), mode, dev)

    #def rmdir(self, path):
    #    pass
        #full_path = self._full_path(path)
        #return os.rmdir(full_path)

    #def mkdir(self, path, mode):
    #    pass
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
    #dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree','f_blocks', 'f_bsize', 
    #'f_favail', 'f_ffree', 'f_files', 'f_flag','f_frsize', 'f_namemax'))

    #def unlink(self, path):
    #    pass
        #return os.unlink(self._full_path(path))
    
    #def symlink(self, name, target):
    #    pass
        #return os.symlink(name, self._full_path(target))
    
    #def rename(self, old, new):
    #    pass
        #return os.rename(self._full_path(old), self._full_path(new))
    
    #def link(self, target, name):
    #    pass
        #return os.link(self._full_path(target), self._full_path(name))
    
    #def utimens(self, path, times=None):
    #    pass
        #return os.utime(self._full_path(path), times)
    
    # File methods
    # ============
    
    def open(self, path, flags):
        path_objs = self.path_to_objects(path)
        if path_objs is None:
            raise FuseOSError(errno.ENOENT)
        if path_objs[-1] not in self.comment_files():
            raise FuseOSError(errno.EISDIR)

        fname, content_num = self.get_content_fnames_wrap(path_objs[-2], path_objs[-1])
        # if we've opened this file before, give back the file descriptor we already have
        if fname in self.open_files:
            return self.open_files[fname]
        # otherwise open the file for the first time and save the file descriptor
        else:
            f, size = open_content(path_objs[-2], fname, content_num, self.max_file_size)
            self.open_files[fname] = f
            self.file_sizes[fname] = size # in case we haven't saved the size already
            return f
        #full_path = self._full_path(path)
        #return os.open(full_path, flags)
    
    #def create(self, path, mode, fi=None):
    #    pass
        #full_path = self._full_path(path)
        #return os.open(full_path, os.O_WRONLY | os.O_CREAT, mode)
    
    def read(self, path, length, offset, fh):
        path_objs = self.path_to_objects(path)
        if path_objs is None:
            raise FuseOSError(errno.ENOENT)
        if path_objs[-1] not in self.comment_files():
            raise FuseOSError(errno.EISDIR)
        os.lseek(fh, offset, os.SEEK_SET)
        return os.read(fh, length)
    
    def write(self, path, buf, offset, fh):
        pass
        #os.lseek(fh, offset, os.SEEK_SET)
        #return os.write(fh, buf)
    
    #def truncate(self, path, length, fh=None):
    #    pass
        #full_path = self._full_path(path)
        #with open(full_path, 'r+') as f:
        #    f.truncate(length)
            
    #def flush(self, path, fh):
    #    pass
        #return os.fsync(fh)

    def release(self, path, fh):
        path_objs = self.path_to_objects(path)
        if path_objs is None:
            raise FuseOSError(errno.ENOENT)
        if path_objs[-1] not in self.comment_files():
            raise FuseOSError(errno.EISDIR)

        fname, content_num = self.get_content_fnames_wrap(path_objs[-2], path_objs[-1])
        if fname in self.open_files:
            os.close(self.open_files[fname])
            os.unlink(fname)
            del self.open_files[fname]

        return None
    
    #def fsync(self, path, fdatasync, fh):
    #    pass
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
    
