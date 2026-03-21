import psycopg2
from flask import Flask, request, make_response, jsonify

app = Flask(__name__)


def open_db_conn():
    try:
        conn = psycopg2.connect(
            host="db",
            database="scrape_db",
            user="conscious_feed",
            password="conscious_feed",
            port=5432,
        )
        return conn
    except Exception as e:
        print(f"error: {e}")
        return None


@app.route("/db_execute", methods=["POST"])
def db_execute():
    conn = open_db_conn()
    if conn is None:
        return make_response("Database connection failed", 500)

    cursor = conn.cursor()
    command = request.form.get("command")
    if not command:
        cursor.close()
        conn.close()
        return make_response("Missing parameter: command", 400)

    cursor.execute(command)
    if cursor.description is None:
        conn.commit()
        cursor.close()
        conn.close()
        return make_response("Command executed successfully", 200)

    ret = cursor.fetchall()
    cursor.close()
    conn.close()
    return make_response(jsonify(ret), 200)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
