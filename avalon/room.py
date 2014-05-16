import jinja2
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

        template = JINJA_ENVIRONMENT.get_template('room.html')
        self.response.write(template.render({'room_name': room_name}))


class RoomStatusPage(webapp2.RequestHandler):
    
    def get(self, room_name):
        state = model.getRoom(room_name).state
        self.response.write(state)


class GameCreatePage(webapp2.RequestHandler):
    
    def get(self, room_name):
        room = model.getRoom(room_name)
        state = room.state
        
        # TODO: Use a transaction to prevent races.
        if state != 'NO_GAME':
            return self.redirect('/' + room_name)
        room.state = 'GAME_BEING_CREATED'
        room.put()
        
        template = JINJA_ENVIRONMENT.get_template('create_game.html')
        self.response.write(template.render({'room_name': room_name}))
    
    def post(self, room_name):
        user = users.get_current_user()
        room = model.getRoom(room_name)
        player_count = self.request.get('player_count')
        if player_count:
            player_count = int(player_count)
        else:
            player_count = 5
        room.game = model.Game(player_count=player_count, owner=user, available_roles=model.ROLES)
        room.state = 'WAITING_FOR_PLAYERS'
        room.put()
        return self.redirect('/' + room_name)


class GamePage(webapp2.RequestHandler):
    
    def get(self, room_name):
        # TODO: Check if we are still looking for players and join if so.
        user = users.get_current_user()
        added = model.addPlayerToGame(room_name, user)
        room = model.getRoom(room_name)
        assignments = room.game.assignments
        role = 'Unknown'
        for assignment in assignments:
            if user == assignment.user:
                role = assignment.role
                break
        if role == 'Unknown' or not added:
            return self.response.write('Could not add you to the game. Sorry.')
        self.response.write('Congrats, you are in the game! Your role is %s.' % role)
    

application = webapp2.WSGIApplication([
    (r'/(\w+)', RoomPage),
    (r'/state/(\w+)', RoomStatusPage),
    (r'/(\w+)/create_game', GameCreatePage),
    (r'/(\w+)/game', GamePage)
    ],
    debug=True)


# TODO remove this?
def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
