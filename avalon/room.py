import jinja2
import json
import os
import model
import random
import webapp2

from google.appengine.api import channel
from google.appengine.ext import ndb
from google.appengine.api import users
from google.appengine.ext.webapp.util import run_wsgi_app


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True
)


class RoomPage(webapp2.RequestHandler):
    
    @staticmethod
    @ndb.transactional
    def add_user(room_name, user):
        room = model.Room.get(room_name)
        room.add_user(user)
        room.put()
    
    def get(self, room_name):
        user = users.get_current_user()
        if not user:
            return self.redirect(users.create_login_url(self.request.uri))
        
        room = model.Room.get(room_name)
        if room.state == 'GAME_BEING_CREATED' and room.owner == user:
            return self.redirect('/' + room_name + '/create_game');
        elif room.game and room.game.includes_user(user):
            return self.redirect('/' + room_name + '/game')
        
        RoomPage.add_user(room_name, user)
        
        token = channel.create_channel(user.user_id() + room_name)
        template_values = {'token': token,
                           'room_name': room_name}

        template = JINJA_ENVIRONMENT.get_template('room.html')
        self.response.write(template.render(template_values))
    
    def post(self, room_name):
        model.Room.notify_all(room_name)


class GameCreatePage(webapp2.RequestHandler):
    
    def get(self, room_name):
        user = users.get_current_user()
        if not user:
            return self.redirect(users.create_login_url(self.request.uri))
        
        if not model.Room.take_ownership(room_name=room_name, user=user):
            return self.redirect('/' + room_name)
        
        model.Room.notify_all(room_name)
        
        room = model.Room.get(room_name)
        template_values = {'room_name': room_name,
                           'nicknames': [u.nickname() for u in room.users]}
        
        template = JINJA_ENVIRONMENT.get_template('create_game.html')
        self.response.write(template.render(template_values))

    @staticmethod
    def validate_form(special_role_count, evil_special_role_count, player_count, evil_role_count):
        if special_role_count > player_count:
            return False
        if evil_special_role_count > evil_role_count:
            return False
        return True
        

    def post(self, room_name):
        user = users.get_current_user()
        if not user:
            return self.redirect(users.create_login_url(self.request.uri))
        
        room = model.Room.get(room_name)
        if room.owner != user:
            return self.redirect('/' + room_name)
        
        roles = []
        special_roles = []
        nicknames = []
        evil_role_count = 0
        for arg in self.request.arguments():
            if arg.endswith('_role') and self.request.get(arg) == 'on':
                special_roles.append(arg[:-len('_role')])
            elif arg.endswith('_name') and self.request.get(arg) == 'on':
                nicknames.append(arg[:-len('_name')])
            elif arg == 'evil_role_count':
                evil_role_count = int(self.request.get(arg))
        
        evil_special_role_count = sum(1 for role in special_roles if role in model.EVIL_SPECIAL_ROLES)
        if not GameCreatePage.validate_form(len(special_roles), evil_special_role_count, len(nicknames), evil_role_count):
            return self.redirect('/' + room_name)
        
        minion_count = evil_role_count - evil_special_role_count
        roles.extend(minion_count * ['minion'])
        loyal_count = len(nicknames) - len(special_roles) - minion_count
        roles.extend(loyal_count * ['loyal'])
        roles.extend(special_roles)
        
        players = []
        for nickname in nicknames:
            for user in room.users:
                if nickname == user.nickname():
                    players.append(user)
                    break
        
        random.shuffle(players)
        
        assignments = []
        available_roles = roles[:]
        for user in players:
            role = random.choice(available_roles)
            available_roles.remove(role)
            assignments.append(model.RoleAssignment(user=user, role=role))
        
        room.game = model.Game(players=players, roles=roles, assignments=assignments)
        room.state = 'GAME_IN_PROGRESS'
        room.put()
        model.Room.notify_all(room_name)
        return self.redirect('/' + room_name)
    

class CancelGameCreatePage(webapp2.RequestHandler):
    
    def post(self, room_name):
        user = users.get_current_user()
        if not user:
            return self.redirect(users.create_login_url(self.request.uri))
        model.Room.relinquish_ownership(room_name, user)
        return self.redirect('/' + room_name)

    
class GameDestroyPage(webapp2.RequestHandler):
    
    def post(self, room_name):
        user = users.get_current_user()
        if not user:
            return self.redirect(users.create_login_url(self.request.uri))
        model.destroy_game(room_name, user)
        self.redirect('/' + room_name)


class GamePage(webapp2.RequestHandler):
    
    def get(self, room_name):
        user = users.get_current_user()
        if not user:
            return self.redirect(users.create_login_url(self.request.uri))
        
        room = model.Room.get(room_name)
        if not room.game or not user in room.game.players:
            return self.redirect('/' + room_name)
        
        template_values = {'room_name': room_name,
                           'role': room.game.get_role(user),
                           'identities': room.game.get_identities(user),
                           'all_roles': room.game.roles}
        
        template = JINJA_ENVIRONMENT.get_template('game.html')
        self.response.write(template.render(template_values))

    
class GameStatusPage(webapp2.RequestHandler):
    
    def get(self, room_name):
        user = users.get_current_user()
        room = model.Room.get(room_name)
        info = {'identities': []}
        if room.game and room.game.assignments:
            if room.game.all_roles:
                info['all_roles'] = room.game.all_roles
                info['mission_params'] = model.MISSION_PARAMETERS[len(room.game.all_roles)]
            if room.game.round_state:
                info['round_state'] = room.game.round_state
                info['leader_index'] = room.game.leader_index
                info['round_number'] = room.game.round_number
                info['round_failed_leader_count'] = room.game.round_failed_leader_count
                if room.game.round_state == 'WAITING_FOR_TEAM_PROPOSAL':
                    if room.game.assignments[room.game.leader_index].user == user:
                        info['you_are_the_leader'] = True
                    info['team_size'] = model.MISSION_PARAMETERS[len(room.game.all_roles)][room.game.round_number]
                elif room.game.round_state == 'VOTING_ON_TEAM':
                    info['team_proposal'] = room.game.team_proposal
                    already_voted = False
                    for vote in room.game.team_proposal_votes:
                        if vote.user == user:
                            already_voted = True
                            break
                    if already_voted:
                        info['vote_needed'] = False
                    else:
                        info['vote_needed'] = True
                elif room.game.round_state == 'MISSION_IN_PROGRESS':
                    if user.nickname() in room.game.team:
                        info['in_team'] = True
                        already_voted = False
                        for vote in room.game.mission_votes:
                            if vote.user == user:
                                already_voted = True
                                break
                        if already_voted:
                            info['vote_needed'] = False
                        else:
                            info['vote_needed'] = True
            info['current_number_of_players'] = len(room.game.assignments)
            info['total_number_of_players'] = room.game.player_count
        return self.response.write(json.dumps(info))
    
    
class SubmitTeamProposalPage(webapp2.RequestHandler):
    
    def post(self, room_name):
        user = users.get_current_user()
        room = model.Room.get(room_name)
        if not user or not room or not room.game or room.game.assignments[room.game.leader_index].user != user:
            return self.redirect('/' + room_name)
        proposal = []
        for item in self.request.params.items():
            # TODO: Make sure these are valid user names. (URL encoded form)
            if item[1] == 'on':
                proposal.append(item[0])
        room.game.team_proposal = proposal
        room.game.round_state = 'VOTING_ON_TEAM'
        room.put()
        return self.redirect('/' + room_name + '/game')


class VoteOnTeamProposal(webapp2.RequestHandler):

    def post(self, room_name):
        user = users.get_current_user()
        room = model.Room.get(room_name)
        if not user or not room or not room.game or room.game.round_state != 'VOTING_ON_TEAM' or user in [v.user for v in room.game.team_proposal_votes]:
            return self.redirect('/' + room_name)
        if not room.game.team_proposal_votes:
            room.game.team_proposal_votes = []
        vote = False
        if self.request.get('team_proposal_vote') == 'yes':
            vote = True
        room.game.team_proposal_votes.append(model.BooleanVote(user=user, vote=vote))
        if len(room.game.team_proposal_votes) == room.game.player_count:
            ayes = 0
            nays = 0
            for vote in room.game.team_proposal_votes:
                if vote.vote:
                    ayes += 1
                else:
                    nays += 1
            room.game.team_proposal_votes = []
            if ayes > nays:
                room.game.round_state = 'MISSION_IN_PROGRESS'
                room.game.round_failed_leader_count = 0
                room.game.team = room.game.team_proposal
            else:
                room.game.leader_index += 1
                room.game.leader_index %= room.game.player_count
                room.game.round_failed_leader_count += 1
                if room.game.round_failed_leader_count >= model.MAX_FAILED_PROPOSAL_COUNT:
                    room.game.round_state = 'WAITING_FOR_TEAM_PROPOSAL'
                    room.game.number_of_missions_failed += 1
                    room.game.round_number += 1
                    room.game.round_failed_leader_count = 0
        room.put()
        return self.redirect('/' + room_name)


class VoteOnMissionSuccess(webapp2.RequestHandler):
    
    def post(self, room_name):
        # TODO: Tally the votes.
        return self.redirect('/' + room_name)


application = webapp2.WSGIApplication([
    (r'/(\w+)', RoomPage),
    (r'/(\w+)/create_game', GameCreatePage),
    (r'/(\w+)/cancel_create_game', CancelGameCreatePage),
    (r'/(\w+)/destroy_game', GameDestroyPage),
    (r'/(\w+)/game', GamePage),
    (r'/(\w+)/game_state', GameStatusPage),
    (r'/(\w+)/submit_team_proposal', SubmitTeamProposalPage),
    (r'/(\w+)/vote_on_team_proposal', VoteOnTeamProposal),
    (r'/(\w+)/vote_on_mission_success', VoteOnMissionSuccess)
    ],
    debug=True)


# TODO remove this?
def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
