import jinja2
import os
import logging
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
        
        token = channel.create_channel(room.get_client_id(user))
        template_values = {'token': token,
                           'room_name': room_name}

        template = JINJA_ENVIRONMENT.get_template('room.html')
        self.response.write(template.render(template_values))
    
    def post(self, room_name):
        room = model.Room.get(room_name)
        room.notify_all()


class GameCreatePage(webapp2.RequestHandler):
    
    def get(self, room_name):
        user = users.get_current_user()
        if not user:
            return self.redirect(users.create_login_url(self.request.uri))
        
        if not model.Room.take_ownership(room_name=room_name, user=user):
            return self.redirect('/' + room_name)
        
        room = model.Room.get(room_name)
        room.notify_all()

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
        

    @ndb.transactional
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
        
        if len(roles) not in model.MISSION_PARAMETERS:
            return self.redirect('/' + room_name)
        
        room.create_game(players=players, roles=roles, assignments=assignments)
        room.put()
        room.notify_all()
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
        
        token = channel.create_channel(room.game.get_client_id(user))
        
        template_values = {'room_name': room_name,
                           'token': token,
                           'role': room.game.get_role(user),
                           'identities': room.game.get_identities(user),
                           'all_roles': room.game.roles,
                           'round_counts': model.MISSION_PARAMETERS[len(room.game.players)]}
        
        template = JINJA_ENVIRONMENT.get_template('game.html')
        self.response.write(template.render(template_values))
    
    def post(self, room_name):
        room = model.Room.get(room_name)
        if room.game:
            room.game.notify_all()

    
class SubmitTeamProposalPage(webapp2.RequestHandler):
    
    @ndb.transactional
    def post(self, room_name):
        user = users.get_current_user()
        if not user:
            return self.redirect(users.create_login_url(self.request.uri))
        
        room = model.Room.get(room_name)
        if not user or not room.game or room.game.players[room.game.leader_index] != user:
            return self.redirect('/' + room_name)
        
        proposal = []
        for item in self.request.params.items():
            valid_nicknames = [u.nickname() for u in room.game.players]
            if item[1] == 'on' and item[0].endswith('_name'):
                nickname = item[0][:-len('_name')]
                if nickname not in valid_nicknames:
                    return self.redirect('/' + room_name)
                proposal.append(nickname)
        
        room.game.round = model.Round()
        room.game.round.team = proposal
        room.game.round.players_yet_to_view_results = room.game.players
        room.game.round.state = 'VOTING_ON_TEAM'
        room.put()
        room.game.notify_all()
        return self.redirect('/' + room_name + '/game')


class VoteOnTeamProposal(webapp2.RequestHandler):
    
    @staticmethod
    def can_vote(room, user):
        if not room.game:
            return False
        if room.game.round.state != 'VOTING_ON_TEAM':
            return False
        if user not in room.game.players:
            return False
        if user in [v.user for v in room.game.round.team_proposal_votes]:
            return False
        return True

    @ndb.transactional
    def post(self, room_name):
        user = users.get_current_user()
        if not user:
            return self.redirect(users.create_login_url(self.request.uri))

        room = model.Room.get(room_name)
        if not VoteOnTeamProposal.can_vote(room, user):
            return self.redirect('/' + room_name)
        
        if not room.game.round.team_proposal_votes:
            room.game.round.team_proposal_votes = []
        vote = False
        if self.request.get('team_proposal_vote') == 'yes':
            vote = True
        
        room.game.round.team_proposal_votes.append(model.BooleanVote(user=user, vote=vote))
        if len(room.game.round.team_proposal_votes) == len(room.game.players):
            room.game.round.state = 'TEAM_VOTE_RESULTS'
        room.put()
        return self.redirect('/' + room_name)


class AcknowledgeTeamVoteResults(webapp2.RequestHandler):
    
    @ndb.transactional
    def post(self, room_name):
        user = users.get_current_user()
        if not user:
            return self.redirect(users.create_login_url(self.request.uri))

        room = model.Room.get(room_name)
        
        if not room.game or not room.game.round or room.game.round.state != 'TEAM_VOTE_RESULTS' or user not in room.game.players:
            return self.redirect('/' + room_name)
        
        if not room.game.round.team_vote_acknowledgers:
            room.game.round.team_vote_acknowledgers = []
        
        if user not in room.game.round.team_vote_acknowledgers:
            room.game.round.team_vote_acknowledgers.append(user)
        
        if len(room.game.round.team_vote_acknowledgers) == len(room.game.players):
            ayes = sum(1 for vote in room.game.round.team_proposal_votes if vote.vote)
            nays = len(room.game.players) - ayes
            if ayes > nays:
                room.game.round.state = 'MISSION_IN_PROGRESS'
            else:
                room.game.round.failed_proposal_count += 1
                if room.game.round.failed_proposal_count >= model.MAX_FAILED_PROPOSAL_COUNT:
                    room.game.failed_mission_count += 1
                    room.game.round.description = 'Mission failed because we could not agree on a team.'
                    room.game.round.state = 'MISSION_OVER'
                else:
                    room.game.leader_index += 1
                    room.game.leader_index %= len(room.game.players)
                    room.game.round.state = 'WAITING_FOR_TEAM_PROPOSAL'
            room.game.round.team_vote_acknowledgers = []
        room.put()
        return self.redirect('/' + room_name)


class VoteOnMissionSuccess(webapp2.RequestHandler):
    
    @ndb.transactional
    def post(self, room_name):
        user = users.get_current_user()
        if not user:
            return self.redirect(users.create_login_url(self.request.uri))
        
        room = model.Room.get(room_name)
        if not room.game or not room.game.round.state == 'MISSION_IN_PROGRESS' or not user.nickname() in room.game.round.team or room.game.round.already_voted_for_mission_outcome(user):
            return self.redirect('/' + room_name)
        
        vote = (self.request.get('mission_success') == 'success')
        room.game.round.mission_votes.append(model.BooleanVote(user=user, vote=vote))
        
        if len(room.game.round.mission_votes) == len(room.game.round.team):
            nays = room.game.round.mission_failure_vote_count()
            nays_needed = model.MISSION_PARAMETERS[len(room.game.players)][room.game.round_number][1]
            if nays >= nays_needed:
                room.game.failed_mission_count += 1
                room.game.round.description = 'Mission failed due to traitor(s)'
            else:
                room.game.round.description = 'Mission succeeded'
            room.game.round.state = 'MISSION_OVER'

        room.put()        
        return self.redirect('/' + room_name)


class AcknowledgeMissionVoteResults(webapp2.RequestHandler):
    
    @ndb.transactional
    def post(self, room_name):
        user = users.get_current_user()
        if not user:
            return self.redirect(users.create_login_url(self.request.uri))
        
        room = model.Room.get(room_name)
        
        if not room.game or not room.game.round or room.game.round.state != 'MISSION_OVER' or user not in room.game.players:
            return self.redirect('/' + room_name)
        
        if not room.game.round.mission_vote_acknowledgers:
            room.game.round.mission_vote_acknowledgers = []
            
        if user not in room.game.round.mission_vote_acknowledgers:
            room.game.round.mission_vote_acknowledgers.append(user)
        
        if len(room.game.round.mission_vote_acknowledgers) == len(room.game.players):
            if room.game.round_number == len(model.MISSION_PARAMETERS[len(room.game.players)]) - 1:
                room.game.round.state = 'CLEANUP'
            else:
                room.game.round_number += 1
                room.game.leader_index += 1
                room.game.leader_index %= len(room.game.players)
                room.game.round = model.Round()
        room.put()
        return self.redirect('/' + room_name)


class AssassinPage(webapp2.RequestHandler):
    
    @ndb.transactional
    def post(self, room_name):
        user = users.get_current_user()
        if not user:
            return self.redirect(users.create_login_url(self.request.uri))
        
        room = model.Room.get(room_name)
        user_is_assassin = False
        for assignment in room.game.assignments:
            if user == assignment.user and 'assassin' == assignment.role:
                user_is_assassin = True
                break
        if not room.game or room.game.round.state != 'CLEANUP' or 'merlin' not in room.game.roles or not user_is_assassin:
            return self.redirect('/' + room_name)
        
        assassin_target = self.request.get('assassin_target')
        merlin_nickname = None
        for assignment in room.game.assignments:
            if assignment.role == 'merlin':
                merlin_nickname = assignment.user.nickname()
        
        if assassin_target == merlin_nickname:
            room.game.assassin_correct = True
        else:
            room.game.assassin_correct = False
        room.game.assassin_done = True
        room.put()
        room.game.notify_all()
        return self.redirect('/' + room_name)


application = webapp2.WSGIApplication([
    (r'/(\w+)', RoomPage),
    (r'/(\w+)/create_game', GameCreatePage),
    (r'/(\w+)/cancel_create_game', CancelGameCreatePage),
    (r'/(\w+)/destroy_game', GameDestroyPage),
    (r'/(\w+)/game', GamePage),
    (r'/(\w+)/submit_team_proposal', SubmitTeamProposalPage),
    (r'/(\w+)/vote_on_team_proposal', VoteOnTeamProposal),
    (r'/(\w+)/acknowledge_team_vote_results', AcknowledgeTeamVoteResults),
    (r'/(\w+)/vote_on_mission_success', VoteOnMissionSuccess),
    (r'/(\w+)/acknowledge_mission_vote_results', AcknowledgeMissionVoteResults),
    (r'/(\w+)/assassin', AssassinPage)
    ],
    debug=True)


# TODO remove this?
def main():
    logging.getLogger().setLevel(logging.DEBUG)
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
