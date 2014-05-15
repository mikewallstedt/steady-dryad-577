import random
import uuid
from google.appengine.ext import ndb

ROLES = ['Minion', 'Merlin', 'Loyal', 'Mordred', 'Morgana', 'Oberon', 'Percival']


class RoleAssignment(ndb.Model):
    user = ndb.UserProperty(required=True)
    role = ndb.StringProperty(choices=ROLES, required=True)


class GameState(ndb.Model):
    game_id = ndb.StringProperty(required=True)
    assignments = ndb.StructuredProperty(RoleAssignment, repeated=True)


class Room(ndb.Model):
    name = ndb.StringProperty(required=True)
    users = ndb.UserProperty(repeated=True)
    game_state = ndb.StructuredProperty(GameState)


def getRoom(room_name):
    return ndb.Key(Room, room_name).get()

@ndb.transactional
def addUserToRoom(room_name, user):
    added = False
    room = getRoom(room_name)
    if not room:
        room = Room(name=room_name, id=room_name)
    if user not in room.users:
        room.users.append(user)
        added = True
    room.put()
    return added

@ndb.transactional
def getGameInfo(room_name):
    retval = {'ready': 'False'}
    room = getRoom(room_name)
    if room and len(room.users) >= 2:
        retval['ready'] = True
        if not room.game_state:
            game_state = GameState(game_id=uuid.uuid4().hex)
            available_roles = ROLES[:]
            for user in room.users:
                role = random.choice(available_roles)
                available_roles.remove(role)
                assignment = RoleAssignment()
                assignment.user = user
                assignment.role = role
                game_state.assignments.append(assignment)
            room.game_state = game_state
            room.put()
        retval['assignments'] = room.game_state.assignments
    if room:
        retval['number_of_users'] = len(room.users)
    return retval