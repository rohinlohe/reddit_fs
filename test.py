import praw
import random
import requests
import pytube
import pyimgur
import json

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

def process_post(obj):
    # self post
    if obj.is_self:
        f = open("temp.txt", "w")
        f.write(obj.selftext)
        f.close()
    else:
        req = requests.get(obj.url)
        assert(req.status_code == 200)
        if req.headers['content-type'] == 'application/pdf':
            f = open("temp.pdf", "w")
            f.write(req.content)
            f.close()
        else:
            if obj.domain == 'youtube.com':
                #f = open("temp.mp4")
                yt = pytube.YouTube(obj.url)
                yt.set_filename("temp_yt")
                qualities = ['144p', '240p', '360p', '480p', '720p', '1080p']
                for q in qualities:
                    videos = yt.filter('mp4', q)
                    if len(videos) == 1:
                        break
                video = videos[0]
                video.download("")
            elif obj.domain == 'imgur.com': # TODO: might run into problems if we try downloading a gif from imgur
                im = pyimgur.Imgur(CLIENT_ID)
                url = obj.url
                url = url.split("/")[-1]
                image = im.get_image(url)
                # not specifying path means that the image will be downloaded in current
                # working directory
                str(image.download(path="", name="temp_img", overwrite=True, size=None)) #typecast as string to convert from unicode
            elif obj.domain == 'streamable.com':
                id = obj.url.split("/")[-1]
                req = requests.get("http://api.streamable.com/videos/" + id)
                assert(req.status_code == 200)
                video_info = json.loads(req.content)
                mp4_req = requests.get("http:" + video_info['files']['mp4']['url'])
                f = open("temp_stream.mp4", "w")
                f.write(mp4_req.content)
                f.close()
            else:
                f = open("temp.html", "w")
                f.write(req.content)
                f.close()


    #print req.text
    #print req.headers['content-type'] #application/pdf, 
    #for cont in req.iter_content:
    #    print cont
        
r = praw.Reddit("testing /u/sweet_n_sour_curry", api_request_delay=1.0)
self_sub = r.get_submission(submission_id="4e8z8t") #4e8q3w
pdf_sub = r.get_submission(submission_id="3ui1d4")
otherlink_sub = r.get_submission(submission_id="4e7u4e")
youtube_sub = r.get_submission(submission_id="4e5pmj")
streamable_sub = r.get_submission(submission_id="4e8gw4")

print list(first_n(5))
print list(random_nums())
print list(random_nums2())
process_post(self_sub)
process_post(pdf_sub)
process_post(otherlink_sub)
process_post(youtube_sub)
process_post(streamable_sub)

"""
submission = r.get_submission(submission_id = "4deewb")
comments = submission.comments
print find_comment(comments, "d1qi66m")"""
#all_comments = get_all_comments(comments)
#print len(all_comments)

