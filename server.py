import sys
import json
import flask
import gevent.pywsgi
import gevent.monkey
import pymongo
import requests
import uuid
import servicehub
import zhixue

gevent.monkey.patch_all()

app = flask.Flask(__name__)
cfg = {}
ctx = servicehub.Context("172.16.8.1:6619")
db = pymongo.MongoClient("127.0.0.1", 27017).HydroCloud_StudentIDService

with open(sys.argv[1], "rb") as f:
    cfg = json.loads(f.read().decode("utf-8"))

class Session:
    def __init__(self, user_id, username):
        self.token = str(uuid.uuid4())
        self.user_id = user_id
        self.username = username

class User:
    def __init__(self, id = "", name = "", status = 0):
        self.id = id
        self.name = name
        self.status = status
    
    @staticmethod
    def get_by_id(id):
        u = db.users.find_one({
            "id": id
        })
        if u == None:
            return None
        return User(id = id, name = u["name"], status = u["status"])
    
    def update(self):
        return db.users.update_one({
            "id": self.id
        }, {
            "$set": {
                "status": self.status
            }
        })
    
    def insert(self):
        return db.users.insert_one({
            "id": self.id,
            "name": self.name,
            "status": self.status
        })
    
    def update_or_insert(self):
        r = self.update()
        if r.matched_count == 0:
            self.insert()

class Student:
    def __init__(self, user_id = "", name = "", student_id = "", school_id = "", school_name = "", class_id = "", class_name = ""):
        self.user_id = user_id
        self.name = name
        self.student_id = student_id

        self.school_id = school_id
        self.school_name = school_name

        self.class_id = class_id
        self.class_name = class_name
    
    @staticmethod
    def get_by_user_id(id):
        u = db.students.find_one({
            "user_id": id
        })
        if u == None:
            return None
        return Student(
            user_id = id,
            name = u["name"],
            student_id = u["student_id"],
            school_id = u["school_id"],
            school_name = u["school_name"],
            class_id = u["class_id"],
            class_name = u["class_name"]
        )
    
    @staticmethod
    def load_from_zhixue_login_response(user_id, resp):
        if resp["errorCode"] != 0:
            raise Exception("Login failed")
        r = resp["result"]
        return Student(
            user_id = user_id,
            name = r["name"],
            student_id = r["userInfo"]["studentNo"],
            school_id = r["userInfo"]["school"]["schoolId"],
            school_name = r["userInfo"]["school"]["schoolName"],
            class_id = r["clazzInfo"]["id"],
            class_name = r["clazzInfo"]["name"]
        )
    
    def update(self):
        return db.students.update_one({
            "user_id": self.user_id
        }, {
            "$set": {
                "name": self.name,
                "student_id": self.student_id,
                "school_id": self.school_id,
                "school_name": self.school_name,
                "class_id": self.class_id,
                "class_name": self.class_name
            }
        })
    
    def insert(self):
        return db.students.insert_one({
            "user_id": self.user_id,
            "name": self.name,
            "student_id": self.student_id,
            "school_id": self.school_id,
            "school_name": self.school_name,
            "class_id": self.class_id,
            "class_name": self.class_name
        })
    
    def update_or_insert(self):
        r = self.update()
        if r.matched_count == 0:
            self.insert()
    
    def remove(self):
        return db.students.delete_one({
            "user_id": self.user_id
        })

sessions = {}

@app.route("/api/user/login", methods = ["POST"])
def on_api_user_login():
    client_token = flask.request.form["client_token"]

    r = requests.post("https://oneidentity.me/identity/verify/verify_client_token", data = {
        "client_token": client_token
    }).json()
    if r["err"] != 0:
        return flask.jsonify({
            "err": 1,
            "msg": "Verification failed"
        })

    u = User.get_by_id(r["userId"])
    if u == None:
        u = User(id = r["userId"], name = r["username"])
        u.insert()
    
    sess = Session(r["userId"], r["username"])
    sessions[sess.token] = sess
    resp = flask.make_response()
    resp.set_cookie("token", sess.token)
    resp.set_data(json.dumps({
        "err": 0,
        "msg": "OK"
    }))
    return resp

@app.route("/api/user/info", methods = ["POST"])
def on_api_user_info():
    sess = sessions.get(flask.request.cookies["token"], None)
    if sess == None:
        return flask.jsonify({
            "err": 1,
            "msg": "Session not found"
        })
    
    u = User.get_by_id(sess.user_id)
    
    return flask.jsonify({
        "err": 0,
        "msg": "OK",
        "user_id": sess.user_id,
        "username": sess.username,
        "user_status": u.status
    })

@app.route("/api/user/verify/zhixue", methods = ["POST"])
def on_api_user_verify_zhixue():
    sess = sessions.get(flask.request.cookies["token"], None)
    if sess == None:
        return flask.jsonify({
            "err": 1,
            "msg": "Session not found"
        })
    
    r = zhixue.login(flask.request.form["username"], flask.request.form["password"])
    try:
        student_info = Student.load_from_zhixue_login_response(sess.user_id, r)
    except:
        return flask.jsonify({
            "err": 2,
            "msg": "Login failed"
        })
    
    student_info.update_or_insert()

    u = User.get_by_id(sess.user_id)
    u.status = 1
    u.update()

    return flask.jsonify({
        "err": 0,
        "msg": "OK",
        "name": student_info.name,
        "school_name": student_info.school_name,
        "class_name": student_info.class_name
    })

@app.route("/api/student/info", methods = ["POST"])
def on_api_student_info():
    sess = sessions.get(flask.request.cookies["token"], None)
    if sess == None:
        return flask.jsonify({
            "err": 1,
            "msg": "Session not found"
        })
    
    s = Student.get_by_user_id(sess.user_id)
    if s == None:
        return flask.jsonify({
            "err": 2,
            "msg": "Student not found"
        })
    
    return flask.jsonify({
        "err": 0,
        "msg": "OK",
        "name": s.name,
        "school_name": s.school_name,
        "class_name": s.class_name
    })

@app.route("/api/student/remove", methods = ["POST"])
def on_api_student_remove():
    sess = sessions.get(flask.request.cookies["token"], None)
    if sess == None:
        return flask.jsonify({
            "err": 1,
            "msg": "Session not found"
        })

    s = Student.get_by_user_id(sess.user_id)
    if s == None:
        return flask.jsonify({
            "err": 2,
            "msg": "Student not found"
        })
    
    s.remove()

    u = User.get_by_id(sess.user_id)
    u.status = 0
    u.update()

    return flask.jsonify({
        "err": 0,
        "msg": "OK"
    })

@app.route("/")
def on_root():
    token = flask.request.cookies.get("token", None)
    user_id = ""
    username = ""
    user_status = 0
    if token != None:
        sess = sessions.get(token, None)
        if sess != None:
            user_id = sess.user_id
            username = sess.username
            u = User.get_by_id(sess.user_id)
            user_status = u.status
    
    return flask.render_template("general.html",
        user_id = user_id,
        username = username,
        user_status = user_status
    )

ctx.register_with_priority("HydroCloud_StudentIDService", "http://" + cfg["service_addr"] + ":" + str(cfg["service_port"]), cfg["priority"], True)
requests.post(ctx.get_resource_addr("HydroCloud_WebServiceDispatcher_Core") + "/register", json = {
    "domain": cfg["public_domain"],
    "service_name": "HydroCloud_StudentIDService"
})
gevent.pywsgi.WSGIServer(("0.0.0.0", cfg["service_port"]), app).serve_forever()
