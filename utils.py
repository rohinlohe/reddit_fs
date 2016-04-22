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
            if ext == 'jpeg':
                ext = 'jpg'
            fnames.append(base_fname + str(i + 1) + '.' + ext)
    # otherwise, we have a single image
    else:
        # chop off the extension if there is one to get the imgur ID
        id = url_pieces[-1][:url_pieces[-1].find('.')]
        print "ID IS", id, "URL PIECES IS", url_pieces
        img = im.get_image(id)
        # img.type will be like 'image/jpg', we just want the jpg part
        ext = str(img.type.split('/')[-1])
        if ext == 'jpeg':
            ext = 'jpg'
        fnames.append(base_fname + '.' + ext)
    print "FNAMES IS", fnames, "MAX FILES IS", max_num_files
    return fnames, ext    

def get_content_fnames(obj, max_num_files):
    #if type(obj) == type(""):
    #    return None
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

def handle_bad_url(url, fnames):
    # handle the case where we have a bad url
    #assert(len(fname) == 1)
    files = []
    f = open(fnames[0], "w")
    error_str = "could not reach requested URL\n" + str(url)
    f.write(error_str)
    files.append(f)
    sizes = [len(error_str)]
    return files, fnames, sizes

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

def handle_imgur(obj, fnames, content_num, max_size):
    files, sizes = [], []
    # TODO: might run into problems if we try downloading a gif from imgur
    # TODO: imgur urls can end with .gifv (or other extension) in which case we
    # can download them directly
    fname = fnames[content_num]
    im = pyimgur.Imgur(CLIENT_ID)
    url = obj.url
    url_pieces = url.split("/")
    # check if we have an album
    if url_pieces[-2] == 'a':
        print "album"
        album = im.get_album(url_pieces[-1])
        image = album.images[content_num]
        for img in album.images:
            sizes.append(img.size)
    else:
        image = im.get_image(url_pieces[-1])
    print image.link
    # not specifying path means that the image will be downloaded in current
    # working directory
    #str(image.download(name=fnames[content_num][:-4], overwrite=True)) #typecast as string to convert from unicode
    
    image.download(name=fname[:-4], overwrite=True)
    f = open(fname, "r")
    files = [None for x in range(len(fnames))]
    files[content_num] = f
    #sizes = [os.stat(fname).st_size]
    # TODO figure out size
    return files, fnames, sizes

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
        f = open(fnames[0], "w")
        f.write(mp4_req.content)
        files.append(f)
    return files, fnames, sizes

def handle_arbitrary_domain(obj, fnames, max_size):
    files = []
    req = requests.get(obj.url)
    sizes = [len(req.content)]
    if sizes[0] < max_size:
        f = open(fnames[0], "w")
        f.write(req.content)
        files.append(f)
    return files, fnames, sizes

def open_content(obj, content_num=0, max_size=float('inf'), max_num_files=float('inf')):
    #if type(obj) == type(""):
    #    return None
    assert(content_num <= max_num_files)
    files, size = [], None
    fnames, ext = get_content_fnames(obj, max_num_files)
    # we have a comment
    if type(obj) == praw.objects.Comment:
        files, fnames, size = handle_comment(obj, fnames, max_size)
    # we have a self post
    elif obj.is_self:
        files, fnames, size = handle_self_post(obj, fnames, max_size)
    else:
        # if our extension to the filename is .txt, we must have gotten a status
        # code other than 200 in our get_content_fname() function
        #if ext == '.txt':
        #    files, fnames, size = handle_bad_url(obj.url, fnames)
        # otherwise check if we are in one of our supported domains
        if ext == '.pdf':#req.headers['content-type'] == 'application/pdf':
            files, fnames, size = handle_pdf(obj, fnames, max_size)
        elif obj.domain == 'youtube.com' or obj.domain == 'youtu.be':
            files, fnames, size = handle_youtube(obj, fnames, max_size)
        elif obj.domain == 'imgur.com' or obj.domain == 'i.imgur.com':
            files, fnames, size = handle_imgur(obj, fnames, content_num, max_size)
        elif obj.domain == 'streamable.com':
            files, fnames, size = handle_streamable(obj, fnames, max_size)
        elif obj.domain == 'gfycat.com':
            files, fnames, size = handle_gfycat(obj, fnames, max_size)
        else:
            try:
                req = urllib2.urlopen(obj.url)
                files, fnames, size = handle_arbitrary_domain(obj, fnames, max_size)
            except urllib2.HTTPError:
                #return [base_fname + '.txt'], '.txt'
                files, fnames, sizes = handle_bad_url(obj.url, fnames)

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
    #self_sub = r.get_submission(submission_id="4e8z8t") #4e8q3w
    #pdf_sub = r.get_submission(submission_id="3ui1d4")
    #youtube_sub = r.get_submission(submission_id="4e5pmj")
    #streamable_sub = r.get_submission(submission_id="4e8gw4")
    #gfycat_sub = r.get_submission(submission_id="4egtz7")
    #otherlink_sub = r.get_submission(submission_id="4eg3df")
    bad_url_sub = r.get_submission(submission_id="4fumb2")
    imgur_sub = r.get_submission(submission_id="4ei4da")  #4eift7 gifv
    #soundcloud_sub = r.get_submission(submission_id="4eaxqt")
    
    #open_content(self_sub)
    #open_content(pdf_sub)
    #open_content(youtube_sub)
    #open_content(streamable_sub)
    #open_content(gfycat_sub)
    #open_content(otherlink_sub)
    open_content(bad_url_sub)
    open_content(imgur_sub)
    open_content(imgur_sub, 1)
    open_content(imgur_sub, 2)
    open_content(imgur_sub, 3)
    open_content(imgur_sub, 4)

