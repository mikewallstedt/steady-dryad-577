import uuid
import webapp2
from google.appengine.ext.webapp.util import run_wsgi_app


HTML = """
<!doctype html>
<html>
  <head>
    <title>Avalon</title>
  </head>
  <body>
    <form method="post" action="/" >
      Enter Room Name: <input type="text" name="room_name">
      <input type="submit" value="Join">
    </form>
  </body>
</html>
"""

class MainPage(webapp2.RequestHandler):
    
    def get(self):
        self.response.write(HTML)

    def post(self):
        room_name = self.request.get('room_name')
        if not room_name:
            room_name = uuid.uuid4().hex
        self.redirect('/' + room_name)


application = webapp2.WSGIApplication([('/', MainPage)], debug=True)


def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
