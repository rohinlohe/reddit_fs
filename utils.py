import praw
import random
import requests
import pytube
import pyimgur
import json
import os
import urllib2
import re

CLIENT_ID = "5eb8e583972827f"


def find_comment(comments, comment_id):
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

def test_gen():
    base = 'content'
    extensions = ['.jpg', '.png', '.txt', '.mp4', '.gif', '.pdf', '.hmtl']
    for i in range(100):
        for ext in extensions:
            yield base + str(i) + ext
        
"""def get_all_comments(comments):
    all_comments = []
    for comment in comments:
        if type(comment) == praw.objects.MoreComments and comment.count > 0:
            print "GOING DOWN", comment, comment.comments()
            all_comments.extend(get_all_comments(comment.comments()))
        else:
            all_comments.append(comment)
    return all_comments
"""

def get_gfycat_id(url):
    id = ""
    start = url[url.find("gfycat.com") + 11:]
    for c in start:
        if c.isalpha():
           id += c
        else:
            break
    return id

def get_content_fnames(obj):
    #if type(obj) == type(""):
    #    return None
    mp4_domains = ['youtube.com', 'youtu.be', 'streamable.com', 'gfycat.com']
    if type(obj) == praw.objects.Comment: 
        return ['comment' + obj.id + '.txt'], '.txt'
    elif obj.is_self:
        return ['submission' + obj.id + '.txt'], '.txt'
    # check that we can access the URL, we give a txt file if we can't
    # we use urllib2's urlopen function since it is less likely to give problems
    # with a YouTube link
    req = urllib2.urlopen(obj.url)
    base_fname = 'submission' + obj.id
    try:
        assert(req.getcode() == 200)
    except AssertionError:
        return [base_fname + '.txt'], '.txt'
    if req.headers['content-type'] == 'application/pdf':
        return [base_fname + '.pdf'], '.pdf'
    elif obj.domain in mp4_domains:
        return [base_fname + '.mp4'], '.mp4'
    elif obj.domain == 'imgur.com' or obj.domain == 'i.imgur.com':
        # get the number of pictures in the album
        return [base_fname + '.jpg'], '.jpg'
    else:
        return [base_fname + '.html'], '.html'

def handle_bad_url(url, fnames):
    # handle the case where we have a bad url
    assert(len(fnames) == 1)
    fname = fnames[0]
    f = open(fname, "w")
    error_str = "could not reach requested URL\n" + obj.url
    f.write(error_str)
    size = len(error_str)
    return [f], fnames, [size]

def handle_comment(obj, fnames, max_size):
    sizes = [len(obj.body)]
    files = []
    if sizes[0] < max_size:
        f = open(fnames[0], "w")
        f.write(obj.body)
        files.append(f)
    return files, fnames, sizes

def handle_self_post(obj, fnames, max_size):
    files = []
    sizes = [len(obj.selftext) + len(obj.title) + 1]
    if sizes[0] < max_size:
        f = open(fnames[0], "w")
        f.write(obj.title + '\n')
        f.write(obj.selftext)
        files.append(f)
    return files, fnames, sizes


def handle_pdf(obj, fnames, max_size):
    req = requests.get(obj.url)
    files = []
    sizes = [req.headers['content-length']]
    if sizes[0] > max_size:
        f = open(fnames[0], "wb")
        f.write(req.content)
        files.append(f)
    return files, fnames, sizes
        
def handle_youtube(obj, fnames, max_size):
    files = []
    yt = pytube.YouTube(obj.url)
    yt.set_filename(fnames[0])
    qualities = ['144p', '240p', '360p', '480p', '720p', '1080p']
    for q in qualities:
        videos = yt.filter('mp4', q)
        if len(videos) == 1:
            break
    video = videos[0]
    req = urllib2.urlopen(video.url)
    content = req.read()
    sizes = [len(content)]
    if sizes[0] < max_size:
        f = open(fnames[0], 'wb')
        f.write(content)
        files.append(f)
    return files, fnames, sizes

def handle_imgur(obj, fname, max_size):
    f = None
    # TODO: might run into problems if we try downloading a gif from imgur
    # TODO: imgur urls can end with .gifv (or other extension) in which case we
    # can download them directly
    im = pyimgur.Imgur(CLIENT_ID)
    url = obj.url
    url_pieces = re.split('\.|\/', imgur_sub.url)
    url = url.split("/")[-1]
    # check if we have an album
    if url[-2] == 'a':
        pass
    image = im.get_image(url)
    # not specifying path means that the image will be downloaded in current
    # working directory
    str(image.download(path="", name=fname[:len(fname) - 4], overwrite=True, size=None)) #typecast as string to convert from unicode
    f = open(fname, "r")
    size = os.stat(fname).st_size
    # TODO figure out size
    return f, fname, size

def handle_streamable(obj, fnames, max_size):
    files = []
    # get the id of the video and make API request
    id = obj.url.split("/")[-1]
    req = requests.get("http://api.streamable.com/videos/" + id)
    assert(req.status_code == 200)
    # figure out the url of the mp4 version of the video and download it
    video_info = json.loads(req.content)
    sizes = [video_info['files']['mp4']['size']]
    if sizes[0] < max_size:
        mp4_req = requests.get("http:" + video_info['files']['mp4']['url'])
        f = open(fnames[0],"w")
        f.write(mp4_req.content)
        files.append(f)
    return files, fnames, sizes

def handle_gfycat(obj, fnames, max_size):
    files = []
    # first request gives back json about the gif
    gfycat_id = get_gfycat_id(obj.url)
    gfycat_req = requests.get("https://gfycat.com/cajax/get/" + gfycat_id)
    assert(gfycat_req.status_code == 200)
    gfycat_info = json.loads(gfycat_req.content)
    sizes = [gfycat_info['gfyItem']['mp4Size']]
    print sizes[0], max_size, sizes[0] < max_size
    if sizes[0] < max_size:
        print "a"
        # download the contents from the mp4 URL
        mp4_url = gfycat_info['gfyItem']['mp4Url']
        print "b"
        mp4_req = requests.get(mp4_url)
        print "here:"
        assert(mp4_req.status_code == 200)
        f = open(fname, "w")
        f.write(mp4_req.content)
        files.append(f)
    return files, fnames, sizes

def handle_arbitrary_domain(obj, fname, max_size):
    f = None
    req = requests.get(obj.url)
    size = len(req.content)
    if size < max_size:
        f = open(fname, "w")
        f.write(req.content)
    return f, fname, size

def open_content(obj, max_size=float('inf')):
    #if type(obj) == type(""):
    #    return None
    files, size = [], None
    fnames, ext = get_content_fnames(obj)
    # we have a comment
    if type(obj) == praw.objects.Comment:
        files, fnames, size = handle_comment(obj, fnames, max_size)
    # we have a self post
    elif obj.is_self:
        files, fnames, size = handle_self_post(obj, fnames, max_size)
    else:
        # if our extension to the filename is .txt, we must have gotten a status
        # code other than 200 in our get_content_fname() function
        if ext == '.txt':
            files, fnames, size = handle_bad_url(obj.url, fnames)
        # otherwise check if we are in one of our supported domains
        elif ext == '.pdf':#req.headers['content-type'] == 'application/pdf':
            files, fnames, size = handle_pdf(obj, fnames, max_size)
        elif obj.domain == 'youtube.com' or obj.domain == 'youtu.be':
            files, fnames, size = handle_youtube(obj, fnames, max_size)
        elif obj.domain == 'imgur.com' or obj.domain == 'i.imgur.com':
            files, fnames, size = handle_imgur(obj, fnames, max_size)
        elif obj.domain == 'streamable.com':
            files, fnames, size = handle_streamable(obj, fnames, max_size)
        elif obj.domain == 'gfycat.com':
            files, fnames, size = handle_gfycat(obj, fnames, max_size)
        else:
            files, fnames, size = handle_arbitrary_domain(obj, fnames, max_size)

    #if files != []:
    # close the python file objects and then reopen with os.open to give back
    # file descriptors
    for f, fname in zip(files, fnames):
        f.close()
        files.remove(f)
        files.append(os.open(fname, os.O_RDONLY))
    return files, fnames, size

def test_g():
    [(yield x) for x in range(5)]

if __name__ == "__main__":
    r = praw.Reddit("testing /u/sweet_n_sour_curry", api_request_delay=1.0)
    self_sub = r.get_submission(submission_id="4e8z8t") #4e8q3w
    pdf_sub = r.get_submission(submission_id="3ui1d4")
    #youtube_sub = r.get_submission(submission_id="4e5pmj")
    streamable_sub = r.get_submission(submission_id="4e8gw4")
    gfycat_sub = r.get_submission(submission_id="4egtz7")
    """otherlink_sub = r.get_submission(submission_id="4eg3df")
    imgur_sub = r.get_submission(submission_id="4ei4da") #album 4eift7"""
    

    #soundcloud_sub = r.get_submission(submission_id="4eaxqt")

    
    #print list(first_n(5))
    #print list(random_nums())
    #print list(random_nums2())
    #f1, fname1, size = open_content(imgur_sub)

    
    open_content(self_sub)
    open_content(pdf_sub)
    #open_content(youtube_sub)
    open_content(streamable_sub)
    open_content(gfycat_sub)
    """open_content(otherlink_sub)
    open_content(imgur_sub)"""
    #process_post(soundcloud_sub)

    #print f1, fname1, size
    #print get_content_fname(imgur_sub)
    """
    submission = r.get_submission(submission_id = "4deewb")
    comments = submission.comments
    print find_comment(comments, "d1qi66m")"""
    #all_comments = get_all_comments(comments)
    #print len(all_comments)
    for x in test_g():
        print x
        #print x in test_gen()

