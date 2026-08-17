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
                response = json.load(raw_response)

                self.port = response.get("assigned_port")
                self.bandwidth = response.get("bandwidth")
                self.file_content = response.get("file")
                print(f"[+] Connected to server! Port: {self.port} | Bandwidth: {self.bandwidth} Mbps")

                if not self.file_content:
                    self.server_file_list = response.get("file_name")
        except Exception as e:
            print(f"[-] Failed to register to server: {e}")

if __name__ == "__main__":
    print("Welcome to ParallelPulse!")
    print("Registering with server...")
    peer = Peer()
    peer.register_to_server()
    

