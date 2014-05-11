import jinja2
import os
import webapp2

from google.appengine.api import users
from google.appengine.ext import ndb
from google.appengine.ext.webapp.util import run_wsgi_app


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True
)


class Room(ndb.Model):
    room_name = ndb.StringProperty(required=True)
    users = ndb.UserProperty(repeated=True)

    @classmethod
    def query_room(cls, room_name):
        rooms = cls.query(ancestor=room_key(room_name)).fetch(1)
        return rooms[0] if rooms else None


def room_key(room_name):
    return ndb.Key('room', room_name)


class RoomPage(webapp2.RequestHandler):
    
        
    def get(self, room_name):
        user = users.get_current_user();
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
            return
        
        template = JINJA_ENVIRONMENT.get_template('room.html')
        self.response.write(template.render({'room_name': room_name}))

        room = Room.query_room(room_name)
        if not room:
            room = Room(parent=room_key(room_name))
            room.room_name = room_name
        room.users.append(user)
        room.put()
        

class RoomStatusPage(webapp2.RequestHandler):
    
    def get(self, room_name):
        room = Room.query_room(room_name)
        if room and len(room.users) > 2:
            self.response.out.write('Ready!')
        else:
            self.response.out.write('Not ready')


application = webapp2.WSGIApplication([
    (r'/(\w+)', RoomPage),
    (r'/ready/(\w+)', RoomStatusPage),    
    ],
    debug=True)


def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
