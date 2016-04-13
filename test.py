import praw
import random
import requests
import pytube
import pyimgur
import json
import os

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

def random_nums():
    nums = []
    yield 42
    for i in range(4):
        nums.append(random.randint(0, 1000))
    [(yield n) for n in nums]

def random_nums2():
    #nums = []
    yield 1, 2, 3
    for i in range(4):
        #nums.append(random.randint(0, 1000))
        yield random.randint(0, 1000)
    return

def first_n(n):
    num = 0
    while num < n:
        #yield from random_nums()
        #for i in random_nums():
        #    yield i
        random_nums2()
        yield num
        num += 1

def get_gfycat_id(url):
    id = ""
    print url
    start = url[url.find("gfycat.com") + 11:]
    for c in start:
        if c.isalpha():
           id += c
        else:
            break
    return id

def get_content_fname(obj):
    if type(obj) == type(""):
        return None
    mp4_domains = ['youtube.com', 'streamable.com', 'gfycat.com']
    if type(obj) == praw.objects.Comment or obj.is_self:
        return 'comment' + obj.id + '.txt', '.txt'
    # check that we can access the URL, we give a txt file if we can't
    req = requests.get(obj.url)
    base_fname = 'submission' + obj.id
    try:
        assert(req.status_code == 200)
    except AssertionError:
        return base_fname + '.txt', '.txt'
    if req.headers['content-type'] == 'application/pdf':
        return base_fname + '.pdf', '.pdf'
    elif obj.domain in mp4_domains:
        return base_fname + '.mp4', '.mp4'
    else:
        return base_fname + '.html', '.html'

def open_content(obj):
    if type(obj) == type(""):
        return None
    f, size = None, None
    fname = get_content_fname(obj)[0]
    if type(obj) == praw.objects.Comment:
        #fname = 'comment' + obj.id + '.txt'
        f = open(fname, "w")
        f.write(obj.body)
        size = len(obj.body)
    # self post
    elif obj.is_self:
        #fname = "submission" + obj.id + '.txt'
        f = open(fname, "w")
        f.write(obj.title + '\n')
        f.write(obj.selftext)
        size = len(obj.selftext) + len(obj.title)
        #extension = '.txt'
    else:
        req = requests.get(obj.url)
        try:
            assert(req.status_code == 200)
        except AssertionError:
            #fname = "submission" + obj.id + '.txt'
            f = open(fname, "w")
            error_str = "could not reach requested URL\n" + obj.url
            f.write(error_str)
            size = len(error_str)
            return f, fname, error_str
        if req.headers['content-type'] == 'application/pdf':
            #fname = "submission" + obj.id + '.pdf'
            f = open(fname, "w")
            f.write(req.content)
            size = len(req.content)
        else:
            if obj.domain == 'youtube.com':
                #f = open("temp.mp4")
                yt = pytube.YouTube(obj.url)
                yt.set_filename("submission" + obj.id)
                qualities = ['144p', '240p', '360p', '480p', '720p', '1080p']
                for q in qualities:
                    videos = yt.filter('mp4', q)
                    if len(videos) == 1:
                        break
                video = videos[0]
                video.download("")
                #fname = "submission" + obj.id + '.mp4'
                f = open(fname, "w")
                size = os.stat(fname)['st_size']
            elif obj.domain == 'imgur.com': # TODO: might run into problems if we try downloading a gif from imgur
                im = pyimgur.Imgur(CLIENT_ID)
                url = obj.url
                url = url.split("/")[-1]
                image = im.get_image(url)
                # not specifying path means that the image will be downloaded in current
                # working directory
                str(image.download(path="", name="submission" + obj.id, overwrite=True, size=None)) #typecast as string to convert from unicode
                # TODO figure out size
            elif obj.domain == 'streamable.com':
                # get the id of the video and make API request
                id = obj.url.split("/")[-1]
                req = requests.get("http://api.streamable.com/videos/" + id)
                assert(req.status_code == 200)
                # figure out the url of the mp4 version of the video and download it
                video_info = json.loads(req.content)
                mp4_req = requests.get("http:" + video_info['files']['mp4']['url'])
                #fname = "submission" + obj.id + ".mp4"
                f = open(fname,"w")
                f.write(mp4_req.content)
                size = len(req.content)
            elif obj.domain == 'gfycat.com':
                # first request gives back json about the gif
                gfycat_id = get_gfycat_id(obj.url)
                gfycat_req = requests.get("https://gfycat.com/cajax/get/" + gfycat_id)
                assert(req.status_code == 200)
                gfycat_info = json.loads(gfycat_req.content)
                # download the contents from the mp4 URL
                mp4_url = gfycat_info['gfyItem']['mp4Url']
                mp4_req = requests.get(mp4_url)
                assert(mp4_req.status_code == 200)
                #fname = "submission" + obj.id + ".mp4"
                f = open(fname, "w")
                f.write(mp4_req.content)
                size = len(mp4_req.content)
                #extension = '.mp4'
            else:
                #fname = "submission" + obj.id + ".html"
                f = open(fname, "w")
                f.write(req.content)
                size = len(req.content)

    # close the python file object and then reopen with os.open to give back a
    # file descriptor
    f.close()
    f = os.open(fname, os.O_RDONLY)
    return f, fname, size

if __name__ == "__main__":
    r = praw.Reddit("testing /u/sweet_n_sour_curry", api_request_delay=1.0)
    self_sub = r.get_submission(submission_id="4e8z8t") #4e8q3w
    pdf_sub = r.get_submission(submission_id="3ui1d4")
    otherlink_sub = r.get_submission(submission_id="4eg3df")
    youtube_sub = r.get_submission(submission_id="4e5pmj")
    streamable_sub = r.get_submission(submission_id="4e8gw4")
    #soundcloud_sub = r.get_submission(submission_id="4eaxqt")
    gfycat_sub = r.get_submission(submission_id="4egtz7")

    #print list(first_n(5))
    #print list(random_nums())
    #print list(random_nums2())
    f1, fname1, size = open_content(self_sub)
    #process_post(pdf_sub)
    #process_post(otherlink_sub)
    #process_post(youtube_sub)
    #process_post(streamable_sub)
    #process_post(soundcloud_sub)
    #process_post(gfycat_sub)
    print f1, fname1, size
    print get_content_fname(self_sub)
    """
    submission = r.get_submission(submission_id = "4deewb")
    comments = submission.comments
    print find_comment(comments, "d1qi66m")"""
    #all_comments = get_all_comments(comments)
    #print len(all_comments)

