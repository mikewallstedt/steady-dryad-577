import json

from google.appengine.api import channel
from google.appengine.ext import ndb

GOOD_SPECIAL_ROLES = ['merlin', 'percival']
EVIL_SPECIAL_ROLES = ['mordred', 'morgana', 'oberon']
SPECIAL_ROLES = [role for group in (GOOD_SPECIAL_ROLES, EVIL_SPECIAL_ROLES) for role in group]
EVIL_ROLES = [role for group in (EVIL_SPECIAL_ROLES, ['minion']) for role in group]
GOOD_ROLES = [role for group in (GOOD_SPECIAL_ROLES, ['loyal']) for role in group]
ROLES = [role for group in (GOOD_ROLES, EVIL_ROLES) for role in group]

ROOM_STATES = ['NO_GAME', 'GAME_BEING_CREATED', 'GAME_IN_PROGRESS']

ROUND_STATES = ['WAITING_FOR_TEAM_PROPOSAL', 'VOTING_ON_TEAM', 'MISSION_IN_PROGRESS']

DEFAULT_PLAYER_COUNT = 5

MAX_FAILED_PROPOSAL_COUNT = 5

MISSION_PARAMETERS = {5: [[2, 1], [3, 1], [2, 1], [3, 1], [3, 1]],
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
    mission_votes = ndb.StructuredProperty(BooleanVote, repeated=True)


class Game(ndb.Model):
    players = ndb.UserProperty(repeated=True)
    roles = ndb.StringProperty(choices=ROLES, repeated=True)
    assignments = ndb.StructuredProperty(RoleAssignment, repeated=True)

    mission_failure_count = ndb.IntegerProperty(default=0)
    leader_index = ndb.IntegerProperty(default=0)
    round_number = ndb.IntegerProperty(default=0)
    round = ndb.StructuredProperty(Round)
    
    def includes_user(self, user):
        return user in self.players
    
    def get_role(self, user):
        for assignment in self.assignments:
            if assignment.user == user:
                return assignment.role
        return 'unknown'
    
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
    
    @staticmethod
    def notify_all(room_name):
        room = Room.get(room_name)
        owner_nickname = None
        if room.owner:
            owner_nickname = room.owner.nickname()
        message = {'room_state': room.state,
                   'nicknames_present': [u.nickname() for u in room.users],
                   'owner_nickname': owner_nickname}
        for user in room.users:
            if room.state == 'GAME_IN_PROGRESS' and room.game and user in room.game.players:
                message['in_game'] = True
            else:
                message['in_game'] = False
            channel.send_message(user.user_id() + room_name, json.dumps(message))
    
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
    
@ndb.transactional
def destroy_game(room_name, user):
    room = Room.get(room_name)
    room.state = 'NO_GAME'
    if room.game and room.game.includes_user(user):
        room.game = None
        room.put()
