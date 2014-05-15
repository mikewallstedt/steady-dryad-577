import jinja2
import json
import os
import model
import webapp2

from google.appengine.api import users
from google.appengine.ext.webapp.util import run_wsgi_app


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True
)


class RoomPage(webapp2.RequestHandler):
    
    def get(self, room_name):
        user = users.get_current_user()
        if not user:
            return self.redirect(users.create_login_url(self.request.uri))

        model.addUserToRoom(room_name, user)

        template = JINJA_ENVIRONMENT.get_template('room.html')
        self.response.write(template.render({'room_name': room_name}))


class RoomStatusPage(webapp2.RequestHandler):
    
    def get(self, room_name):
        user = users.get_current_user()
        game_info = model.getGameInfo(room_name)
        if 'assignments' in game_info:
            for assignment in game_info['assignments']:
                if assignment.user == user:
                    role = assignment.role
                    break
            del game_info['assignments']
            game_info['role'] = role
        self.response.write(json.dumps(game_info))
    

application = webapp2.WSGIApplication([
    (r'/(\w+)', RoomPage),
    (r'/ready/(\w+)', RoomStatusPage),    
    ],
    debug=True)


# TODO remove this?
def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
