import random
from google.appengine.ext import ndb

ROLES = ['Minion', 'Merlin', 'Loyal', 'Mordred', 'Morgana', 'Oberon', 'Percival']

ROOM_STATES = ['NO_GAME', 'GAME_BEING_CREATED', 'WAITING_FOR_PLAYERS', 'IN_PROGRESS']


class RoleAssignment(ndb.Model):
    user = ndb.UserProperty(required=True)
    role = ndb.StringProperty(choices=ROLES, required=True)


class Game(ndb.Model):
    player_count = ndb.IntegerProperty(required=True)
    available_roles = ndb.StringProperty(choices=ROLES, repeated=True)
    assignments = ndb.StructuredProperty(RoleAssignment, repeated=True)
    players = ndb.UserProperty(repeated=True)
    owner = ndb.UserProperty(required=True)


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
            already_present = False
            break
    if already_present:
        return False
    role = random.choice(game.available_roles)
    game.assignments.append(RoleAssignment(user=user, role=role))
    game.available_roles.remove(role)
    room.put()
    return True


@ndb.transactional
def getRoomStatus(room_name):
    room = getRoom(room_name)
    return room.status