from contextlib import closing
import sqlite3


class Snippets:
    def __init__(self, database):
        self.database = database
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS snippets "
                "(id INTEGER PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL)"
            )

    def create(self, title, body):
        with closing(sqlite3.connect(self.database)) as connection, connection:
            cursor = connection.execute(
                "INSERT INTO snippets (title, body) VALUES (?, ?)", (title, body),
            )
            snippet_id = cursor.lastrowid
        return snippet_id

    def search(self, words):
        with closing(sqlite3.connect(self.database)) as connection:
            connection.row_factory = sqlite3.Row
            matches = []
            for row in connection.execute(
                "SELECT id, title, body FROM snippets ORDER BY id DESC"
            ):
                title, body = row["title"].casefold(), row["body"].casefold()
                if all(word in title or word in body for word in words):
                    matches.append(dict(row))
            return matches
