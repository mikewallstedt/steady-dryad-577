import jinja2
import json
import os
import model
import webapp2

from google.appengine.api import users
from google.appengine.ext.webapp.util import run_wsgi_app
from model import DEFAULT_PLAYER_COUNT


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
        
        room = model.getRoom(room_name)
        if room.game and room.game.assignments:
            for assignment in room.game.assignments:
                if assignment.user == user:
                    return self.redirect('/' + room_name + '/game')

        template = JINJA_ENVIRONMENT.get_template('room.html')
        self.response.write(template.render({'room_name': room_name}))


class RoomStatusPage(webapp2.RequestHandler):
    
    def get(self, room_name):
        state = model.getRoom(room_name).state
        self.response.write(state)


class GameCreatePage(webapp2.RequestHandler):
    
    def get(self, room_name):
        user = users.get_current_user()
        begun = model.beginGameCreation(room_name, user)
        if not begun:
            return self.redirect('/' + room_name)
        template = JINJA_ENVIRONMENT.get_template('create_game.html')
        self.response.write(template.render({'room_name': room_name}))
    
    def post(self, room_name):
        user = users.get_current_user()
        room = model.getRoom(room_name)
        if not room.game or room.game.owner != user:
            return self.redirect('/' + room_name)
        player_count = self.request.get('player_count')
        if player_count:
            player_count = int(player_count)
        else:
            player_count = DEFAULT_PLAYER_COUNT
        room.game.player_count = player_count
        good_player_count = 0
        evil_player_count = 0
        available_roles = []
        for role in model.SPECIAL_ROLES:
            if self.request.get(role.lower()):
                available_roles.append(role)
                if role in model.GOOD_SPECIAL_ROLES:
                    good_player_count += 1
                else:
                    evil_player_count += 1
        desired_evil_player_count = (player_count + 1) / 3
        while evil_player_count < desired_evil_player_count and evil_player_count + good_player_count < player_count:
            available_roles.append('Minion')
            evil_player_count += 1
        while evil_player_count + good_player_count < player_count:
            available_roles.append('Loyal')
            good_player_count += 1
        room.game.available_roles = available_roles
        room.game.all_roles = available_roles[:]
        room.state = 'WAITING_FOR_PLAYERS'
        room.put()
        return self.redirect('/' + room_name)


class GamePage(webapp2.RequestHandler):
    
    def get(self, room_name):
        user = users.get_current_user()
        if not user:
            return self.redirect('/' + room_name)
        added = model.addPlayerToGame(room_name, user)
        room = model.getRoom(room_name)
        if not room.game:
            return self.redirect('/' + room_name)
        assignments = room.game.assignments
        role = 'Unknown'
        for assignment in assignments:
            if user == assignment.user:
                role = assignment.role
                break
        if role == 'Unknown' or not added:
            return self.response.write('Could not add you to the game. Sorry.')
        template = JINJA_ENVIRONMENT.get_template('game.html')
        self.response.write(template.render({'room_name': room_name, 'role': role}))
    
    
class GameStatusPage(webapp2.RequestHandler):
    
    def get(self, room_name):
        user = users.get_current_user()
        room = model.getRoom(room_name)
        info = {'identities': []}
        if room.game and room.game.assignments:
            if room.game.all_roles:
                info['all_roles'] = room.game.all_roles
            role = "Unassigned"
            for assignment in room.game.assignments:
                if assignment.user == user:
                    role = assignment.role
            info['current_number_of_players'] = len(room.game.assignments)
            info['total_number_of_players'] = room.game.player_count
            evil_roles = model.EVIL_SPECIAL_ROLES + ['Minion']
            if role == 'Merlin':
                for assignment in room.game.assignments:
                    nickname = assignment.user.nickname()
                    if assignment.user == user:
                        info['identities'].append([nickname, 'me'])
                    elif assignment.role in evil_roles and assignment.role != 'Mordred':
                        info['identities'].append([nickname, 'evil'])
                    else:
                        info['identities'].append([nickname, 'unknown'])
            elif role == 'Percival':
                for assignment in room.game.assignments:
                    nickname = assignment.user.nickname()
                    if assignment.user == user:
                        info['identities'].append([nickname, 'me'])
                    elif assignment.role == 'Merlin' or assignment.role == 'Morgana':
                        identity = 'Merlin'
                        if 'Morgana' in room.game.all_roles:
                            identity = "Merlin (or Morgana)"
                        info['identities'].append([nickname, identity])
                    else:
                        info['identities'].append([nickname, 'unknown'])
            elif role in evil_roles and role != 'Oberon':
                for assignment in room.game.assignments:
                    nickname = assignment.user.nickname()
                    if assignment.user == user:
                        info['identities'].append([nickname, 'me'])
                    elif assignment.role in evil_roles and assignment.role != 'Oberon':
                        info['identities'].append([nickname, 'evil'])
                    else:
                        info['identities'].append([nickname, 'unknown'])
            else:
                for assignment in room.game.assignments:
                    nickname = assignment.user.nickname()
                    if assignment.user == user:
                        info['identities'].append([nickname, 'me'])
                    else:
                        info['identities'].append([nickname, 'unknown'])
        return self.response.write(json.dumps(info))
    

class GameDestroyPage(webapp2.RequestHandler):
    
    def post(self, room_name):
        user = users.get_current_user()
        model.destroyGame(room_name, user)
        self.redirect('/' + room_name)


application = webapp2.WSGIApplication([
    (r'/(\w+)', RoomPage),
    (r'/state/(\w+)', RoomStatusPage),
    (r'/(\w+)/create_game', GameCreatePage),
    (r'/(\w+)/destroy_game', GameDestroyPage),
    (r'/(\w+)/game', GamePage),
    (r'/(\w+)/game_state', GameStatusPage)
    ],
    debug=True)


# TODO remove this?
def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
