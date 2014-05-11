import jinja2
import os
import model
from model import GameState, RoleAssignment, Room
import random
import uuid
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
        user = users.get_current_user();
        if not user:
            self.redirect(users.create_login_url(self.request.uri))
            return
        
        template = JINJA_ENVIRONMENT.get_template('room.html')
        self.response.write(template.render({'room_name': room_name}))

        room = Room.Query(room_name)
        if not room:
            room = Room(parent=Room.GetKey(room_name))
            room.room_name = room_name
        room.users.append(user)
        room.put()
        

class RoomStatusPage(webapp2.RequestHandler):
    
    def get(self, room_name):
        room = Room.Query(room_name)
        if self._IsReady(room):
            if room.game_state is None:
                room.game_state = self._CreateNewGameState(room)
                room.put()
            self.response.out.write('READY - %s' % room.game_state)
        else:
            self.response.out.write('NOT_READY - %s' % room.users)

    def _IsReady(self, room):
        return room and len(room.users) >= 2

    def _CreateNewGameState(self, room):
        game_state = GameState(parent=GameState.GetKey(uuid.uuid4().hex))
        for user in room.users:
            assignment = RoleAssignment(parent=RoleAssignment.GetKey(uuid.uuid4().hex))
            assignment.user = user
            assignment.role = random.choice(model.ROLES)
            game_state.assignments.append(assignment)
        return game_state


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
