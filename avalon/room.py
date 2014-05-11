from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app


HTML = """
<!doctype html>
<html>
  <body>
    <form action="/sign" method="post">
      <div><textarea name="content" rows="3" cols="60"></textarea></div>
      <div><input type="submit" value="Sign Guestbook"></div>
    </form>
  </body>
</html>
"""

class MainPage(webapp.RequestHandler):
    
        
    def get(self, room_id):
#         self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write("room " + room_id)


application = webapp.WSGIApplication([(r'/(\w+)', MainPage)], debug=True)


def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
