from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app


HTML = """
<!doctype html>
<html>
  <head>
    <script src="http://ajax.googleapis.com/ajax/libs/jquery/1.11.0/jquery.min.js"></script>
  </head>  
  <body>
    <form method="get" id="room_selector" >
      Room: <input type="text" id="room_id"/>
      <input type="submit" id="room_submit" value="Join" onclick="gotoYourRoom()"/>
    </form>

    <script type="text/javascript">
      function gotoYourRoom() {
        document.forms[0].action=document.getElementById('room_id').value;
      }
    </script>
  </body>
</html>
"""

class MainPage(webapp.RequestHandler):
    
        
    def get(self):
#         self.response.headers['Content-Type'] = 'text/plain'
        self.response.write(HTML)


application = webapp.WSGIApplication([('/', MainPage)], debug=True)


def main():
    run_wsgi_app(application)

if __name__ == "__main__":
    main()
