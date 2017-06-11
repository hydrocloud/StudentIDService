import requests
import json
import time

ONEIDENTITY_PREFIX = "https://oneidentity.me"

class DomainController:
    def __init__(self, token):
        self.token = token
    
    def on_join(self, user_id, form):
        return {
            "ok": False
        }
    
    def on_quit(self, user_id):
        return {
            "ok": False
        }
    
    def add_user(self, user_id):
        resp = requests.post(ONEIDENTITY_PREFIX + "/services/api/domain/add_user", data = {
            "token": self.token,
            "userId": user_id
        }).json()
        return resp
    
    def remove_user(self, user_id):
        resp = requests.post(ONEIDENTITY_PREFIX + "/services/api/domain/remove_user", data = {
            "token": self.token,
            "userId": user_id
        }).json()
        return resp
    
    def run(self):
        while True:
            try:
                print("[oneidentity_dc] Polling...")
                resp = requests.post(ONEIDENTITY_PREFIX + "/services/api/domain/controller/poll", data = {
                    "token": self.token
                }).json()

                data = resp["update"]
                if data == None:
                    continue
                
                result = {}

                try:
                    if data["action"] == "join":
                        result = self.on_join(data["userId"], data.get("form", None))
                    elif data["action"] == "quit":
                        result = self.on_quit(data["userId"])
                    else:
                        result = {
                            "ok": False,
                            "msg": "Action not implemented"
                        }
                except:
                    result = {
                        "ok": False,
                        "msg": "Exception caught during request handling"
                    }
                
                requests.post(ONEIDENTITY_PREFIX + "/services/api/domain/controller/send_response", data = {
                    "token": self.token,
                    "data": json.dumps(result)
                })
            except:
                time.sleep(3)
