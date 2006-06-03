import logging

import cherrypy

import turbogears
from turbogears import controllers, expose, validate, redirect

from markuptest import json

log = logging.getLogger("markuptest.controllers")

class Root(controllers.RootController):
    @expose(template="markuptest.templates.welcome")
    def index(self):
        import time
        log.debug("Happy TurboGears Controller Responding For Duty")
        return dict(now=time.ctime())
