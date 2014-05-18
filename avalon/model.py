import random
from google.appengine.ext import ndb

GOOD_SPECIAL_ROLES = ['Merlin', 'Percival']
EVIL_SPECIAL_ROLES = ['Mordred', 'Morgana', 'Oberon']
SPECIAL_ROLES = [role for group in (GOOD_SPECIAL_ROLES, EVIL_SPECIAL_ROLES) for role in group]
ROLES = [role for group in (['Minion', 'Loyal'], SPECIAL_ROLES) for role in group]

ROOM_STATES = ['NO_GAME', 'GAME_BEING_CREATED', 'WAITING_FOR_PLAYERS', 'GAME_IN_PROGRESS']

ROUND_STATES = ['WAITING_FOR_TEAM_PROPOSAL', 'VOTING_ON_TEAM', 'MISSION_IN_PROGRESS']

DEFAULT_PLAYER_COUNT = 5

MAX_FAILED_LEADER_COUNT = 5

MISSION_PARAMETERS = {5: [[2, 1], [3, 1], [2, 1], [3, 1], [3, 1]],
              6: [[2, 1], [3, 1], [4, 1], [3, 1], [4, 1]],
              7: [[2, 1], [3, 1], [3, 1], [4, 2], [4, 1]],
              8: [[3, 1], [4, 1], [4, 1], [5, 2], [5, 1]],
              9: [[3, 1], [4, 1], [4, 1], [5, 2], [5, 1]],
              10: [[3, 1], [4, 1], [4, 1], [5, 2], [5, 1]]}


class RoleAssignment(ndb.Model):
    user = ndb.UserProperty(required=True)
    role = ndb.StringProperty(choices=ROLES, required=True)


class Vote(ndb.Model):
    user = ndb.UserProperty(required=True)
    vote = ndb.BooleanProperty(required=True)


class Game(ndb.Model):
    player_count = ndb.IntegerProperty(required=True)
    available_roles = ndb.StringProperty(choices=ROLES, repeated=True)
    all_roles = ndb.StringProperty(choices=ROLES, repeated=True)
    assignments = ndb.StructuredProperty(RoleAssignment, repeated=True)
    owner = ndb.UserProperty(required=True)
    leader_index = ndb.IntegerProperty()
    round_number = ndb.IntegerProperty()
    round_state = ndb.StringProperty(choices=ROUND_STATES)
    round_failed_leader_count = ndb.IntegerProperty()
    team_proposal = ndb.StringProperty(repeated=True)
    team_proposal_votes = ndb.StructuredProperty(Vote, repeated=True)
    team = ndb.StringProperty(repeated=True)
    mission_votes = ndb.StructuredProperty(Vote, repeated=True)
    number_of_missions_failed = ndb.IntegerProperty()


class Room(ndb.Model):
    state = ndb.StringProperty(choices=ROOM_STATES, required=True)
    game = ndb.StructuredProperty(Game)


@ndb.transactional
def getRoom(room_name):
    room = ndb.Key(Room, room_name).get()
    if not room:
        room = Room(id=room_name, state='NO_GAME')
    return room


@ndb.transactional
def addPlayerToGame(room_name, user):
    room = ndb.Key(Room, room_name).get()
    if not room or not room.game:
        return False
    game = getRoom(room_name).game
    already_present = False
    for assignment in game.assignments:
        if assignment.user == user:
            already_present = True
            break
    if already_present:
        return True
    if not game.available_roles:
        return False
    role = random.choice(game.available_roles)
    game.assignments.append(RoleAssignment(user=user, role=role))
    game.available_roles.remove(role)
    if not game.available_roles:
        # All roles are filled. Start the game.
        # Create a random leadership order.
        random.shuffle(game.assignments)
        game.leader_index = 0
        game.round_number = 0
        game.round_state = 'WAITING_FOR_TEAM_PROPOSAL'
        game.round_failed_leader_count = 0
        game.number_of_missions_failed = 0
    room.put()
    return True


@ndb.transactional
def beginGameCreation(room_name, user):
    room = ndb.Key(Room, room_name).get()
    if not room:
        room = Room(id=room_name, state='NO_GAME')
    if room.state == 'NO_GAME':
        room.state = 'GAME_BEING_CREATED'
        room.game = Game(owner=user, player_count=DEFAULT_PLAYER_COUNT)
        room.put()
        return True
    elif room.state == 'GAME_BEING_CREATED' and room.game.owner == user:
        return True
    else:
        return False


@ndb.transactional
def destroyGame(room_name, user):
    room = ndb.Key(Room, room_name).get()
    if room and room.game and room.game.assignments:
        for assignment in room.game.assignments:
            if assignment.user == user:
                room.game = None
                room.state = 'NO_GAME'
                room.put()