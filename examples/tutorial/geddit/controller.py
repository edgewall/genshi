#!/usr/bin/env python

import operator
import os
import pickle
import sys

import cherrypy
from formencode import Invalid
from genshi.filters import HTMLFormFiller
from paste.evalexception.middleware import EvalException

from geddit.form import SubmissionForm, CommentForm
from geddit.lib import template
from geddit.model import Submission, Comment


class Root(object):

    def __init__(self, data):
        self.data = data

    @cherrypy.expose
    @template.output('index.html')
    def index(self):
        return template.render(
            submissions=sorted(self.data.values(),
                               key=operator.attrgetter('time'),
                               reverse=True)
        )

    @cherrypy.expose
    @template.output('info.html')
    def info(self, code):
        submission = self.data.get(code)
        if not submission:
            raise cherrypy.NotFound()
        return template.render(submission=submission)

    @cherrypy.expose
    @template.output('submit.html')
    def submit(self, cancel=False, **data):
        if cherrypy.request.method == 'POST':
            if cancel:
                raise cherrypy.HTTPRedirect('/')
            form = SubmissionForm()
            try:
                data = form.to_python(data)
                submission = Submission(**data)
                self.data[submission.code] = submission
                raise cherrypy.HTTPRedirect('/')
            except Invalid, e:
                errors = e.unpack_errors()
        else:
            errors = {}

        return template.render(errors=errors) | HTMLFormFiller(data=data)

    @cherrypy.expose
    @template.output('comment.html')
    def comment(self, code, cancel=False, **data):
        submission = self.data.get(code)
        if not submission:
            raise cherrypy.NotFound()
        if cherrypy.request.method == 'POST':
            if cancel:
                raise cherrypy.HTTPRedirect('/info/%s' % submission.code)
            form = CommentForm()
            try:
                data = form.to_python(data)
                comment = submission.add_comment(**data)
                raise cherrypy.HTTPRedirect('/info/%s' % submission.code)
            except Invalid, e:
                errors = e.unpack_errors()
        else:
            errors = {}

        return template.render(submission=submission, comment=None,
                               errors=errors) | HTMLFormFiller(data=data)


def main(filename):
    # load data from the pickle file, or initialize it to an empty list
    if os.path.exists(filename):
        fileobj = open(filename, 'rb')
        try:
            data = pickle.load(fileobj)
        finally:
            fileobj.close()
    else:
        data = {}

    def _save_data():
        # save data back to the pickle file
        fileobj = open(filename, 'wb')
        try:
            pickle.dump(data, fileobj)
        finally:
            fileobj.close()
    cherrypy.engine.on_stop_engine_list.append(_save_data)

    # Some global configuration; note that this could be moved into a configuration file
    cherrypy.config.update({
        'request.throw_errors': True,
        'tools.encode.on': True, 'tools.encode.encoding': 'utf-8',
        'tools.decode.on': True,
        'tools.trailing_slash.on': True,
        'tools.staticdir.root': os.path.abspath(os.path.dirname(__file__)),
    })

    # Initialize the application, and add EvalException for more helpful error messages
    app = cherrypy.Application(Root(data))
    app.wsgiapp.pipeline.append(('paste_exc', EvalException))
    cherrypy.quickstart(app, '/', {
        '/media': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': 'static'
        }
    })

if __name__ == '__main__':
    import formencode
    formencode.api.set_stdtranslation(languages=['en'])
    main(sys.argv[1])
