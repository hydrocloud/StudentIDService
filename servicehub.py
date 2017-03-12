import requests
import threading
import time

class ResourceAddrInfo:
    def __init__(self, addr):
        self.addr = addr
        self.create_time = int(time.time() * 1000)
    
    def expired(self):
        if int(time.time() * 1000) - self.create_time > 180000:
            return True
        return False

class Context:
    def __init__(self, hub_addr):
        if hub_addr.startswith("http://") == False and hub_addr.startswith("https://") == False:
            hub_addr = "http://" + hub_addr

        self.hub_addr = hub_addr
        self.resource_addr_cache = {}
    
    def get_resource_addr(self, name):
        if name in self.resource_addr_cache:
            if self.resource_addr_cache[name].expired():
                del self.resource_addr_cache[name]
            else:
                return self.resource_addr_cache[name].addr
        
        r = requests.post(self.hub_addr + "/service/call", json = {
            "service_name": name
        })
        if r.status_code != 200:
            return None

        d = r.json()
        if d == None or d["error_code"] != 0:
            return None

        resource_addr = d["resource_addr"]
        if resource_addr.startswith("http://") == False and resource_addr.startswith("https://") == False:
            resource_addr = "http://" + resource_addr
        
        self.resource_addr_cache[name] = ResourceAddrInfo(resource_addr)
        return resource_addr
    
    def register_with_priority(self, name, addr, resource_priority, keep_alive):
        requests.post(self.hub_addr + "/service/register", json = {
            "service_name": name,
            "resource_addr": addr,
            "resource_priority": resource_priority
        })
        if keep_alive == True:
            threading.Thread(target = self.forever_renew_reg, args = (name, addr, resource_priority)).start()
    
    def register(self, name, addr, keep_alive):
        self.register_with_priority(name, addr, 0, keep_alive)
    
    def forever_renew_reg(self, name, addr, resource_priority):
        while True:
            time.sleep(60)
            try:
                self.register_with_priority(name, addr, resource_priority, False)
            except:
                pass
