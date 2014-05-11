from google.appengine.ext import ndb

ROLES = ['Minion', 'Merlin', 'Loyal', 'Mordred', 'Morgana', 'Oberon', 'Percival']


class RoleAssignment(ndb.Model):
    user = ndb.UserProperty(required=True)
    role = ndb.StringProperty(choices=ROLES, required=True)

    @classmethod
    def GetKey(cls, assignment_id):
        return ndb.Key('role_assignment', assignment_id)


class GameState(ndb.Model):
    assignments = ndb.StructuredProperty(RoleAssignment, repeated=True)

    @classmethod
    def Query(cls, game_id):
        return _GetSingleResult(cls.query(ancestor=cls.GetKey(game_id)).fetch(1))

    @classmethod
    def GetKey(cls, game_id):
        return ndb.Key('game_state', game_id)


class Room(ndb.Model):
    room_name = ndb.StringProperty(required=True)
    users = ndb.UserProperty(repeated=True)
    game_state = ndb.StructuredProperty(GameState)

    @classmethod
    def Query(cls, room_name):
        return _GetSingleResult(cls.query(ancestor=cls.GetKey(room_name)).fetch(1))

    @classmethod
    def GetKey(cls, room_name):
        return ndb.Key('room', room_name)
    

def _GetSingleResult(l):
    return l[0] if l else None