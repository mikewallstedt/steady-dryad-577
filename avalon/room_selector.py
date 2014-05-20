import jinja2
import os
import uuid
import webapp2

from google.appengine.ext.webapp.util import run_wsgi_app


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True
)

class MainPage(webapp2.RequestHandler):
    
    def get(self):
        template = JINJA_ENVIRONMENT.get_template('room_selector.html')
        self.response.write(template.render())

    def post(self):
        room_name = self.request.get('room_name')
        if not room_name:
            room_name = uuid.uuid4().hex
        self.redirect('/' + room_name)


application = webapp2.WSGIApplication([('/', MainPage)], debug=True)


def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
