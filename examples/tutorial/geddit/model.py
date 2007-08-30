from datetime import datetime


class Submission(object):

    def __init__(self, username, url, title):
        self.username = username
        self.url = url
        self.title = title
        self.time = datetime.utcnow()
        self.code = hex(hash(tuple([username, url, title, self.time])))[2:]
        self.comments = []

    def __repr__(self):
        return '<%s %r>' % (type(self).__name__, self.title)

    def add_comment(self, username, content):
        self.comments.append(Comment(username, content))


class Comment(object):

    def __init__(self, username, content):
        self.username = username
        self.content = content
        self.time = datetime.utcnow()

    def __repr__(self):
        return '<%s>' % (type(self).__name__)
