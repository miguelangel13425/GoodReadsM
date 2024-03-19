import uuid
from urllib.parse import parse_qsl, urlparse
from http.server import BaseHTTPRequestHandler, HTTPServer
import re
import redis
from http.cookies import SimpleCookie

redis_storage = redis.Redis()

mappings = [
    (r"^/books/(?P<book_id>\d+)$", "get_book"),
    (r"^/book/(?P<book_id>\d+)$", "get_book"),
    (r"^/$", "index"),
    (r"^/search", "search"),
]

class WebRequestHandler(BaseHTTPRequestHandler):

    @property
    def query_data(self):
        return dict(parse_qsl(self.url.query))

    @property
    def url(self):
        return urlparse(self.path)

    def search(self):
        terms = self.query_data.get('q', '').split()
        matching_books = []

        # Buscar libros en Redis que coincidan con los términos de búsqueda
        for term in terms:
            keys = redis_storage.keys(f"*{term}*")
            matching_books.extend(redis_storage.mget(keys))

        # Generar la página de resultados de búsqueda
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        result_page = f"<h1>Resultados de la búsqueda:</h1><ul>"
        for book in matching_books:
            result_page += f"<li>{book}</li>"
        result_page += "</ul>"
        self.wfile.write(result_page.encode("utf-8"))

    def get_params(self, pattern, path):
        match = re.match(pattern, path)
        if match:
            return match.groupdict()
    
    def index(self, **_):
        session_id = self.get_session()
        print(session_id)
        self.write_session_cookie(session_id)

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        index_page = """
        <h1>Bienvenidos a la biblioteca!</h1>
        <form action="/search" method="get">
        <label for="q">Search</label>
        <input type="text" name="q"/>
        <input type="submit" value="Buscar libros"/>
        </form>
        <p>Su número de sesión es: {}</p>
        """.format(session_id)
        self.wfile.write(index_page.encode("utf-8"))


    def get_book(self, book_id):
        session_id = self.get_session()
        redis_storage.lpush(f"session:{session_id}", f"book:{book_id}")

        # Obtener la lista de libros visitados por el usuario
        visited_books = redis_storage.lrange(f"session:{session_id}", 0, -1)

        # Si el usuario ha visitado tres libros, agregar uno nuevo al principio de la lista
        if len(visited_books) >= 3:
            new_book_id = "new_book_id"
            redis_storage.lpush(f"session:{session_id}", f"book:{new_book_id}")

    def get_session(self):
        cookies = SimpleCookie(self.headers.get('Cookie'))
        session_id = None
        if 'session_id' not in cookies:
            session_id = str(uuid.uuid4())
        else:
            session_id = cookies['session_id'].value
        return session_id

    def write_session_cookie(self, session_id):
        cookies = SimpleCookie()
        cookies["session_id"] = session_id
        cookies["session_id"]["max-age"] = 10  # Duración de la cookie en segundos
        self.send_header("Set-Cookie", cookies["session_id"].OutputString())

    def do_GET(self):
        self.url_mapping_response()

    def url_mapping_response(self):
        for pattern, method in mappings:
            match = self.get_params(pattern, self.url.path)
            if match is not None:
                md = getattr(self, method)
                md(**match)
                return

        self.send_response(404)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write("Not found".encode("utf-8"))

if __name__ == "__main__":
    server_address = ("", 8000)
    httpd = HTTPServer(server_address, WebRequestHandler)
    print("Server running at localhost:8000...")
    httpd.serve_forever()

