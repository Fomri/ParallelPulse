import socket
import json
import threading

SERVER_IP = '127.0.0.1'
SERVER_PORT = 5000
class Peer:
    def __init__(self):
        self.port = None
        self.bandwidth = None
        self.server_file_list = []
        self.file_content = None
    def register_to_server(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((SERVER_IP, SERVER_PORT))
                request = {"action" : "CONNECT"} #if the server gets this message he knows new peer request to register.
                s.sendall(json.dumps(request).encode('utf-8'))

                raw_response = s.recv(4096).decode('utf-8')
                response = json.loads(raw_response)

                self.port = response.get("assigned_port")
                self.bandwidth = response.get("bandwidth")
                self.file_content = response.get("file")
                print(f"[+] Connected to server! Port: {self.port} | Bandwidth: {self.bandwidth} Mbps")

                if not self.file_content:
                    self.server_file_list.append(response.get("file_name"))
        except Exception as e:
            print(f"[-] Failed to register to server: {e}")


    def request_file(self, file_name):
        """
        asks the server for tell what peers hold the file and their information
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((SERVER_IP, SERVER_PORT))
                
                request = {
                    "action": "QUERY",
                    "file_name": file_name
                }
                s.sendall(json.dumps(request).encode('utf-8'))

                raw_response = s.recv(4096).decode('utf-8')
                response = json.loads(raw_response)

                if response.get("status") == "SUCCESS":
                    peers = response.get("peers", [])
                    print(f"[+] Found {len(peers)} peers holding '{file_name}':")
                    for p in peers:
                        print(f"    - IP: {p.get('ip')}, Port: {p.get('port')}, Bandwidth: {p.get('bandwidth')} Mbps")
                    #from here we need to calculate allocation and then request for chunks.
                    return peers
                else:
                    print(f"[-] File query failed: {response.get('message')}")
                    return []

        except Exception as e:
            print(f"[-] Error querying file from server: {e}")
            return []

        
if __name__ == "__main__":
    print("Welcome to ParallelPulse!")
    print("Registering with server...")
    peer = Peer()
    peer.register_to_server()


