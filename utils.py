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

def get_gfycat_id(url):
    id = ""
    start = url[url.find("gfycat.com") + 11:]
    for c in start:
        if c.isalpha():
           id += c
        else:
            break
    return id

def handle_imgur_names(obj, base_fname, max_num_files):
    fnames = []
    url = obj.url
    url_pieces = url.split("/")
    im = pyimgur.Imgur(CLIENT_ID)
    # check if we have an album
    if url_pieces[-2] == 'a':
        album = im.get_album(url_pieces[-1])
        # add a name for each image in the album, but no more than max_num_files
        for i in range(min(len(album.images), max_num_files)):
            ext = str(album.images[i].type.split('/')[-1])
            ext = '.' + ext
            if ext == '.jpeg':
                ext = '.jpg'
            elif ext == '.gif':
                ext = '.mp4'
            fnames.append(base_fname + str(i + 1) + ext)
    # otherwise, we have a single image
    else:
        # chop off the extension if there is one to get the imgur ID
        period_loc = url_pieces[-1].find('.')
        if period_loc < 0:
            id = url_pieces[-1]
        else:
            id = url_pieces[-1][:period_loc]
        img = im.get_image(id)
        # img.type will be like 'image/jpg', we just want the jpg part
        ext = str(img.type.split('/')[-1])
        ext = '.' + ext
        if ext == '.jpeg':
            ext = '.jpg'
        elif ext == '.gif':
            ext = '.mp4'
        fnames.append(base_fname + ext)
    return fnames, ext    

def get_content_fnames(obj, max_num_files):
    mp4_domains = ['youtube.com', 'youtu.be', 'streamable.com', 'gfycat.com']
    if type(obj) == praw.objects.Comment: 
        return ['comment' + obj.id + '.txt'], '.txt'
    elif obj.is_self:
        return ['submission' + obj.id + '.txt'], '.txt'
    base_fname = 'submission' + obj.id
    if obj.domain in mp4_domains:
        return [base_fname + '.mp4'], '.mp4'
    elif obj.domain == 'imgur.com' or obj.domain == 'i.imgur.com':
        return handle_imgur_names(obj, base_fname, max_num_files)
    else:
        try:
            # if we won't be able to give back a content file, we will just
            # give a .txt file saying so
            req = urllib2.urlopen(obj.url)
        except urllib2.HTTPError:
            return [base_fname + '.txt'], '.txt'
        if req.headers['content-type'] == 'application/pdf':
            return [base_fname + '.pdf'], '.pdf'
        else:
            return [base_fname + '.html'], '.html'

def handle_bad_url(url, fname):
    # handle the case where we have a bad url
    f = open(fname, "wb")
    error_str = ("could not reach requested URL\n" + str(url)).encode('utf-8')
    f.write(error_str)
    size = len(error_str)
    return f, size

def handle_comment(obj, fname, max_size):
    body = obj.body.encode('utf8')
    size = len(body)
    f = None
    if size < max_size:
        f = open(fname, "wb")
        f.write(body)
    return f, size

def handle_self_post(obj, fname, max_size):
    f = None
    title = obj.title.encode('utf-8')
    selftext = obj.selftext.encode('utf-8')
    size = len(title) + len(selftext) + 2 # plus 2 for 2 newlines
    if size < max_size:
        f = open(fname, "wb")
        f.write(title + '\n\n')
        f.write(selftext)
    return f, size


def handle_pdf(obj, fname, max_size):
    req = requests.get(obj.url)
    f = None
    content = req.content.encode('utf-8')
    #size = req.headers['content-length']
    size = len(content)
    if size > max_size:
        f = open(fname, "wb")
        f.write(content)
    return f, size
        
def handle_youtube(obj, fname, max_size):
    f = None
    yt = pytube.YouTube(obj.url)
    yt.set_filename(fname)
    qualities = ['144p', '240p', '360p', '480p', '720p', '1080p']
    for q in qualities:
        videos = yt.filter('mp4', q)
        if len(videos) == 1:
            break
    video = videos[0]
    req = urllib2.urlopen(video.url)
    content = req.read()
    size = len(content)
    if size < max_size:
        f = open(fname, 'wb')
        f.write(content)
    return f, size

def handle_imgur(obj, fname, content_num, max_size):
    f = None
    im = pyimgur.Imgur(CLIENT_ID)
    url = obj.url
    url_pieces = url.split("/")
    # check if we have an album
    if url_pieces[-2] == 'a':
        album = im.get_album(url_pieces[-1])
        image = album.images[content_num]
    else:
        period_loc = url_pieces[-1].find('.')
        if period_loc < 0:
            id = url_pieces[-1]
        else:
            id = url_pieces[-1][:period_loc]
        image = im.get_image(id)
    if image.is_animated:
        size = int(image.mp4_size)
        if size < max_size:
            req = requests.get(image.mp4)
            f = open(fname, 'wb')
            f.write(req.content)
    else:
        size = image.size
        if size < max_size:
            image.download(name=fname[:-4], overwrite=True)
            f = open(fname, "rb")
    return f, size

def handle_streamable(obj, fname, max_size):
    f = None
    # get the id of the video and make API request
    id = obj.url.split("/")[-1]
    req = requests.get("http://api.streamable.com/videos/" + id)
    assert(req.status_code == 200)
    # figure out the url of the mp4 version of the video and download it
    video_info = json.loads(req.content)
    size = [video_info['files']['mp4']['size']]
    if size < max_size:
        mp4_req = requests.get("http:" + video_info['files']['mp4']['url'])
        f = open(fname,"wb")
        f.write(mp4_req.content)
    return f, size

def handle_gfycat(obj, fname, max_size):
    f = None
    # first request gives back json about the gif
    gfycat_id = get_gfycat_id(obj.url)
    gfycat_req = requests.get("https://gfycat.com/cajax/get/" + gfycat_id)
    assert(gfycat_req.status_code == 200)
    gfycat_info = json.loads(gfycat_req.content)
    size = int(gfycat_info['gfyItem']['mp4Size'])
    if size < max_size:
        # download the contents from the mp4 URL
        mp4_url = gfycat_info['gfyItem']['mp4Url']
        mp4_req = requests.get(mp4_url)
        assert(mp4_req.status_code == 200)
        f = open(fname, "wb")
        f.write(mp4_req.content)
    return f, size

def handle_arbitrary_domain(obj, fname, max_size):
    f = None
    req = requests.get(obj.url)
    content = req.content.encode('utf-8')
    size = len(content)
    if size < max_size:
        f = open(fname, "wb")
        f.write(content)
    return f, size

def open_content(obj, fname, content_num=0, max_size=float('inf')):
    f, size = None, None
    ext = fname[fname.find('.'):]
    # we have a comment
    if type(obj) == praw.objects.Comment:
        f, size = handle_comment(obj, fname, max_size)
    # we have a self post
    elif obj.is_self:
        f, size = handle_self_post(obj, fname, max_size)
    else:
        if ext == '.pdf':
            f, size = handle_pdf(obj, fname, max_size)
        elif obj.domain == 'youtube.com' or obj.domain == 'youtu.be':
            f, size = handle_youtube(obj, fname, max_size)
        elif obj.domain == 'imgur.com' or obj.domain == 'i.imgur.com':
            f, size = handle_imgur(obj, fname, content_num, max_size)
        elif obj.domain == 'streamable.com':
            f, size = handle_streamable(obj, fname, max_size)
        elif obj.domain == 'gfycat.com':
            f, size = handle_gfycat(obj, fname, max_size)
        else:
            # if we aren't in one of our supported domains, check if we can access
            # the page and either give the html or a text file explaining that
            # we can't access the page
            try:
                req = urllib2.urlopen(obj.url)
                f, size = handle_arbitrary_domain(obj, fname, max_size)
            except urllib2.HTTPError:
                f, size = handle_bad_url(obj.url, fname)

    # close the python file objects and then reopen with os.open to give back
    # file descriptors
    if not f is None:
        f.close()       
        f = os.open(fname, os.O_RDONLY)
    return f, size

if __name__ == "__main__":
    r = praw.Reddit("testing /u/sweet_n_sour_curry", api_request_delay=1.0)
    #self_sub = r.get_submission(submission_id="4fwxht")
    #pdf_sub = r.get_submission(submission_id="3ui1d4")
    #youtube_sub = r.get_submission(submission_id="4e5pmj")
    #streamable_sub = r.get_submission(submission_id="4e8gw4")
    #gfycat_sub = r.get_submission(submission_id="4egtz7")
    #otherlink_sub = r.get_submission(submission_id="4eg3df")
    #bad_url_sub = r.get_submission(submission_id="4fumb2")
    #imgur_sub = r.get_submission(submission_id="4ei4da")  #4eift7 gifv
    #imgur_sub = r.get_submission(submission_id="4frmex")
    imgur_sub_gif = r.get_submission(submission_id = "4fus57")
    #soundcloud_sub = r.get_submission(submission_id="4eaxqt")
    
    #open_content(self_sub, get_content_fnames(self_sub, 1)[0][0])
    #open_content(pdf_sub, get_content_fnames(pdf_sub, 1)[0][0])
    #open_content(youtube_sub, get_content_fnames(youtube_sub, 1)[0][0])
    #open_content(streamable_sub, get_content_fnames(streamable_sub, 1)[0][0])
    #open_content(gfycat_sub, get_content_fnames(gfycat_sub, 1)[0][0])
    #open_content(otherlink_sub, get_content_fnames(otherlink_sub, 1)[0][0])
    #open_content(bad_url_sub, get_content_fnames(bad_url_sub, 1)[0][0])
    open_content(imgur_sub_gif, get_content_fnames(imgur_sub_gif, 1)[0][0])
    
    #imgur_names, ext = get_content_fnames(imgur_sub, 5)
    #open_content(imgur_sub, imgur_names[0], 0)
    #open_content(imgur_sub, imgur_names[1], 1)
    #open_content(imgur_sub, imgur_names[2], 2)
    #open_content(imgur_sub, imgur_names[3], 3)
    #open_content(imgur_sub, imgur_names[4], 4)

