import json

from google.appengine.api import channel
from google.appengine.ext import ndb

GOOD_SPECIAL_ROLES = ['merlin', 'percival']
EVIL_SPECIAL_ROLES = ['mordred', 'morgana', 'oberon', 'assassin']
SPECIAL_ROLES = [role for group in (GOOD_SPECIAL_ROLES, EVIL_SPECIAL_ROLES) for role in group]
EVIL_ROLES = [role for group in (EVIL_SPECIAL_ROLES, ['minion']) for role in group]
GOOD_ROLES = [role for group in (GOOD_SPECIAL_ROLES, ['loyal']) for role in group]
ROLES = [role for group in (GOOD_ROLES, EVIL_ROLES) for role in group]

ROOM_STATES = ['NO_GAME', 'GAME_BEING_CREATED', 'GAME_IN_PROGRESS']

ROUND_STATES = ['WAITING_FOR_TEAM_PROPOSAL', 'VOTING_ON_TEAM', 'TEAM_VOTE_RESULTS', 'MISSION_IN_PROGRESS', 'MISSION_OVER', 'CLEANUP']

MAX_FAILED_PROPOSAL_COUNT = 5

# TODO Remove 2-player.
MISSION_PARAMETERS = {2: [[1, 1], [2, 2]],
              5: [[2, 1], [3, 1], [2, 1], [3, 1], [3, 1]],
              6: [[2, 1], [3, 1], [4, 1], [3, 1], [4, 1]],
              7: [[2, 1], [3, 1], [3, 1], [4, 2], [4, 1]],
              8: [[3, 1], [4, 1], [4, 1], [5, 2], [5, 1]],
              9: [[3, 1], [4, 1], [4, 1], [5, 2], [5, 1]],
              10: [[3, 1], [4, 1], [4, 1], [5, 2], [5, 1]]}


class RoleAssignment(ndb.Model):
    user = ndb.UserProperty(required=True)
    role = ndb.StringProperty(choices=ROLES, required=True)


class BooleanVote(ndb.Model):
    user = ndb.UserProperty(required=True)
    vote = ndb.BooleanProperty(required=True)


class Round(ndb.Model):
    state = ndb.StringProperty(choices=ROUND_STATES, required=True, default='WAITING_FOR_TEAM_PROPOSAL')
    failed_proposal_count = ndb.IntegerProperty(required=True, default=0)
    team = ndb.StringProperty(repeated=True)
    team_proposal_votes = ndb.StructuredProperty(BooleanVote, repeated=True)
    team_vote_acknowledgers = ndb.UserProperty(repeated=True)
    mission_votes = ndb.StructuredProperty(BooleanVote, repeated=True)
    mission_vote_acknowledgers = ndb.UserProperty(repeated=True)
    description = ndb.StringProperty()
    
    def already_voted_for_mission_outcome(self, user):
        return user in [v.user for v in self.mission_votes]
    
    def mission_failure_vote_count(self):
        return sum(1 for v in self.mission_votes if not v.vote)


class Game(ndb.Model):
    room_name = ndb.StringProperty(required=True)
    setup_only = ndb.BooleanProperty(required=True)
    players = ndb.UserProperty(repeated=True)
    roles = ndb.StringProperty(choices=ROLES, repeated=True)
    assignments = ndb.StructuredProperty(RoleAssignment, repeated=True)
    end_requesters = ndb.UserProperty(repeated=True)

    failed_mission_count = ndb.IntegerProperty(default=0)
    leader_index = ndb.IntegerProperty(default=0)
    round_number = ndb.IntegerProperty(default=0)
    round = ndb.StructuredProperty(Round, default=Round())
    assassin_done = ndb.BooleanProperty(default=False)
    assassin_correct = ndb.BooleanProperty()
    
    def includes_user(self, user):
        return user in self.players
    
    def get_role(self, user):
        for assignment in self.assignments:
            if assignment.user == user:
                return assignment.role
        return 'unknown'
    
    def get_client_id(self, user):
        return user.user_id() + self.room_name + ',game'
    
    def notify_all(self):
        proposals_remaining = MAX_FAILED_PROPOSAL_COUNT - self.round.failed_proposal_count
        if proposals_remaining < 0:
            proposals_remaining = 'Caused mission failure'
        
        message = {'failed_mission_count': self.failed_mission_count,
                   'leader_index': self.leader_index,
                   'round_number': self.round_number,
                   'round_state': self.round.state,
                   'proposals_remaining_count': proposals_remaining,
                   'team': self.round.team,
                   'team_proposal_votes': [[vote.user.nickname(), vote.vote] for vote in self.round.team_proposal_votes],
                   'team_size': MISSION_PARAMETERS[len(self.players)][self.round_number][0],
                   'leader': self.players[self.leader_index].nickname(),
                   'mission_fail_votes': self.round.mission_failure_vote_count(),
                   'round_description': self.round.description,
                   'assassin_done': self.assassin_done,
                   'assassin_correct': self.assassin_correct,
                   'assassin_present': 'assassin' in self.roles,
                   'merlin_present': 'merlin' in self.roles}
        
        if len(self.players) == len(self.end_requesters):
            message['assignments'] = [[a.user.nickname(), a.role] for a in self.assignments]
        
        if self.round.state in ('MISSION_IN_PROGRESS', 'MISSION_OVER'):
            message['team'] = self.round.team
        
        if self.round.state == 'TEAM_VOTE_RESULTS':
            message['team_proposal_votes'] = [[v.user.nickname(), v.vote] for v in self.round.team_proposal_votes]
        
        for user in self.players:
            you_are_the_leader = False
            if user == self.players[self.leader_index]:
                you_are_the_leader = True
            message['you_are_the_leader'] = you_are_the_leader
            
            you_are_on_the_team = False
            if user.nickname() in self.round.team:
                you_are_on_the_team = True
            message['you_are_on_the_team'] = you_are_on_the_team
            
            already_voted_on_team = False
            if user in [v.user for v in self.round.team_proposal_votes]:
                already_voted_on_team = True
            message['already_voted_on_team'] = already_voted_on_team
            
            already_acknowledged_team_vote = False
            if user in self.round.team_vote_acknowledgers:
                already_acknowledged_team_vote = True
            message['already_acknowledged_team_vote'] = already_acknowledged_team_vote
            
            already_voted_on_mission = False
            if user in [v.user for v in self.round.mission_votes]:
                already_voted_on_mission = True
            message['already_voted_on_mission'] = already_voted_on_mission
            
            already_acknowledged_mission_vote = False
            if user in self.round.mission_vote_acknowledgers:
                already_acknowledged_mission_vote = True
            message['already_acknowledged_mission_vote'] = already_acknowledged_mission_vote
            
            you_are_the_assassin = False
            for assignment in self.assignments:
                if assignment.user == user and assignment.role == 'assassin':
                    you_are_the_assassin = True
                    break
            message['you_are_the_assassin'] = you_are_the_assassin
            
            already_requested_end = False
            if user in self.end_requesters:
                already_requested_end = True
            message['already_requested_end'] = already_requested_end

            channel.send_message(self.get_client_id(user), json.dumps(message))
    
    def get_players_seen(self, user):
        players_seen = []
        identities = self.get_identities(user)
        for identity in identities:
            if identity[1] not in ('me', ''):
                players_seen.append(identity[0])
        return players_seen

    def get_identities(self, user):
        me = self.get_role(user)
        identities = []
        if me == 'merlin':
            for assignment in self.assignments:
                nickname = assignment.user.nickname()
                role = assignment.role
                if assignment.user == user:
                    identities.append([nickname, 'me'])
                elif role in EVIL_ROLES and role not in ('mordred', 'oberon'):
                    identities.append([nickname, 'evil'])
                else:
                    identities.append([nickname, ''])
        elif me == 'percival':
            for assignment in self.assignments:
                nickname = assignment.user.nickname()
                role = assignment.role
                if assignment.user == user:
                    identities.append([nickname, 'me'])
                elif role in ['merlin', 'morgana']:
                    identity = 'merlin'
                    if 'morgana' in self.roles:
                        identity = "merlin (or morgana)"
                    identities.append([nickname, identity])
                else:
                    identities.append([nickname, ''])
        elif me in EVIL_ROLES and me != 'oberon':
            for assignment in self.assignments:
                nickname = assignment.user.nickname()
                role = assignment.role
                if assignment.user == user:
                    identities.append([nickname, 'me'])
                elif assignment.role in EVIL_ROLES and assignment.role != 'oberon':
                    identities.append([nickname, 'evil'])
                else:
                    identities.append([nickname, ''])
        else:
            for assignment in self.assignments:
                nickname = assignment.user.nickname()
                if assignment.user == user:
                    identities.append([nickname, 'me'])
                else:
                    identities.append([nickname, ''])
        return identities


class Room(ndb.Model):
    state = ndb.StringProperty(choices=ROOM_STATES, required=True)
    users = ndb.UserProperty(repeated=True)
    owner = ndb.UserProperty()
    game = ndb.StructuredProperty(Game)
    
    @staticmethod
    def get(room_name):
        room = ndb.Key(Room, room_name).get()
        if not room:
            room = Room(id=room_name, state='NO_GAME')
        return room
    
    def get_name(self):
        return self.key.id()
    
    def get_client_id(self, user):
        return user.user_id() + self.get_name()
    
    def notify_all(self):
        owner_nickname = None
        if self.owner:
            owner_nickname = self.owner.nickname()
        message = {'room_state': self.state,
                   'nicknames_present': [u.nickname() for u in self.users],
                   'owner_nickname': owner_nickname}
        for user in self.users:
            if self.state == 'GAME_IN_PROGRESS' and self.game and user in self.game.players:
                message['in_game'] = True
            else:
                message['in_game'] = False
            channel.send_message(self.get_client_id(user), json.dumps(message))
    
    @staticmethod
    @ndb.transactional
    def take_ownership(room_name, user):
        room = Room.get(room_name)
        if room.state == 'NO_GAME':
            room.state = 'GAME_BEING_CREATED'
            room.owner = user
            room.put()
            return True
        else:
            return room.owner == user
    
    @staticmethod
    @ndb.transactional
    def relinquish_ownership(room_name, user):
        room = Room.get(room_name)
        if room.owner == user:
            room.owner = None
            if room.state == 'GAME_BEING_CREATED':
                room.state = 'NO_GAME'
            room.put()
    
    def add_user(self, user):
        if not self.users:
            self.users = []
        if not user in self.users:
            self.users.append(user)
    
    def remove_user(self, user):
        if user in self.users:
            self.users.remove(user)
    
    def create_game(self, players, roles, assignments, setup_only=False):
        self.game = Game(room_name=self.get_name(), players=players, roles=roles, assignments=assignments, setup_only=setup_only)
        self.state = 'GAME_IN_PROGRESS'
    
@ndb.transactional
def destroy_game(room_name, user):
    room = Room.get(room_name)
    room.state = 'NO_GAME'
    if room.game and room.game.includes_user(user):
        room.game = None
        room.put()
