from datetime import datetime


class Submission(object):

    def __init__(self, username, url, title):
        self.username = username
        self.url = url
        self.title = title
        self.time = datetime.utcnow()
        self.comments = []

    def __repr__(self):
        return '<%s %r>' % (type(self).__name__, self.title)

    def add_comment(self, username, content):
        comment = Comment(username, content, in_reply_to=self)
        self.comments.append(comment)
        return comment

    @property
    def code(self):
        uid = tuple([self.username, self.url, self.title, self.time])
        return hex(hash(uid))[2:]

    @property
    def total_comments(self):
        retval = []
        for comment in self.comments:
            retval.append(comment)
            retval.extend(comment.total_replies)
        return retval


class Comment(object):

    def __init__(self, username, content, in_reply_to=None):
        self.username = username
        self.content = content
        self.in_reply_to = in_reply_to
        self.time = datetime.utcnow()
        self.replies = []

    def __repr__(self):
        return '<%s>' % (type(self).__name__)

    def add_reply(self, username, content):
        reply = Comment(username, content, in_reply_to=self)
        self.replies.append(reply)
        return reply

    @property
    def code(self):
        uid = tuple([self.in_reply_to.code, self.username, self.time])
        return hex(hash(uid))[2:]

    @property
    def submission(self):
        ref = self.in_reply_to
        while ref:
            if isinstance(ref, Submission):
                return ref
            ref = ref.in_reply_to

    @property
    def total_replies(self):
        retval = []
        for reply in self.replies:
            retval.append(reply)
            retval.extend(reply.total_replies)
        return retval
