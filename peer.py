import socket
import json
import threading
from crypto_utils import encrypt_chunk, decrypt_chunk

SERVER_IP = '127.0.0.1'
SERVER_PORT = 5000
class Peer:
    def __init__(self):
        self.port = None
        self.bandwidth = None
        self.file_content = None
        self.file_name = None
    def register_to_server(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((SERVER_IP, SERVER_PORT))
                request = {"action" : "CONNECT"} # if the server gets this message it knows a new peer requested to register.
                s.sendall(json.dumps(request).encode('utf-8'))

                raw_response = s.recv(4096).decode('utf-8')
                response = json.loads(raw_response)

                self.port = response.get("assigned_port")
                self.bandwidth = response.get("bandwidth")
                self.file_content = response.get("file")
                self.file_name = response.get("file_name")
                print(f"[+] Connected to server! Port: {self.port} | Bandwidth: {self.bandwidth} Mbps")

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
                    file_size = response.get("file_size")
                    print(f"[+] Found {len(peers)} peers holding '{file_name}':")
                    for p in peers:
                        print(f"    - IP: {p.get('ip')}, Port: {p.get('port')}, Bandwidth: {p.get('bandwidth')} Mbps")
                    return peers, file_size
                else:
                    print(f"[-] File query failed: {response.get('message')}")
                    return [], None

        except Exception as e:
            print(f"[-] Error querying file from server: {e}")
            return [], None


    def calculate_allocation(self, peers, file_size, n=3):
            # picks the n peers with the highest bandwidth, and gives each one a byte range
            # proportional to its share of the total bandwidth among the selected peers
            selected = sorted(peers, key=lambda p: p["bandwidth"], reverse=True)[:n]
            total_bw = sum(p["bandwidth"] for p in selected)

            allocation = {}
            offset = 0
            for i, p in enumerate(selected):
                if i == len(selected) - 1:
                    # last peer gets whatever bytes remain, to avoid rounding gaps
                    share = file_size - offset
                else:
                    share = round((p["bandwidth"] / total_bw) * file_size)

                peer_key = (p["ip"], p["port"])
                allocation[peer_key] = {
                    "range": (offset, offset + share),
                    "bandwidth": p["bandwidth"],
                }
                offset += share

            return allocation

    def request_chunk(self, ip, port, byte_range):
        # connects directly (peer-to-peer) to a peer holding the file and asks for a byte range
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((ip, port))
                request = {
                    "action": "CHUNK_REQUEST",
                    "start": byte_range[0],
                    "end": byte_range[1]
                }
                s.sendall(json.dumps(request).encode('utf-8'))
                raw_response = s.recv(4096).decode('utf-8')
                response = json.loads(raw_response)
                if response.get("status") == "SUCCESS":
                    encrypted_data = response.get("chunk_data")
                    return decrypt_chunk(encrypted_data)
                else:
                    print(f"[-] Chunk request failed: {response.get('message')}")
                    return None
        except Exception as e:
            print(f"[-] Error requesting chunk from {ip}:{port}: {e}")
            return None

    def handle_chunk_request(self, request_data):
        # handles an incoming CHUNK_REQUEST when this peer is the one holding the file
        start = request_data.get("start")
        end = request_data.get("end")
        if self.file_content is None:
            return {"status": "ERROR", "message": "peer does not hold this file"}

        chunk_data = self.file_content[start:end]
        encrypted_data = encrypt_chunk(chunk_data) 
        return {"status": "SUCCESS", "chunk_data": encrypted_data}

    def reassemble(self, chunks_with_ranges, output_path):
        # chunks_with_ranges: list of (start, end, chunk_data) tuples
        # writes the chunks back to a file in the correct byte order
        ordered = sorted(chunks_with_ranges, key=lambda item: item[0])
        with open(output_path, "w") as f:
            for start, end, chunk_data in ordered:
                f.write(chunk_data)

    def start_listening(self):
        # opens a socket on this peer's own assigned port and waits for CHUNK_REQUEST
        # messages from other peers, similar to how the central server listens on port 5000
        peer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        peer_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        peer_socket.bind((SERVER_IP, self.port))
        peer_socket.listen(5)
        print(f"[+] Peer listening for chunk requests on port {self.port}")

        while True:
            client_sock, addr = peer_socket.accept()
            handler = threading.Thread(target=self.handle_incoming_chunk_request, args=(client_sock,))
            handler.daemon = True
            handler.start()

    def handle_incoming_chunk_request(self, client_sock):
        # reads one incoming request and dispatches it to handle_chunk_request
        try:
            raw_data = client_sock.recv(4096).decode('utf-8')
            request_data = json.loads(raw_data)
            if request_data.get("action") == "CHUNK_REQUEST":
                response = self.handle_chunk_request(request_data)
                client_sock.sendall(json.dumps(response).encode('utf-8'))
        except Exception as e:
            print(f"[-] Error handling chunk request: {e}")
        finally:
            client_sock.close()


        
    def list_available_files(self):
        # asks the server for all files in the system, excluding files this peer already holds
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((SERVER_IP, SERVER_PORT))
                request = {"action": "LIST_FILES"}
                s.sendall(json.dumps(request).encode('utf-8'))
                raw_response = s.recv(4096).decode('utf-8')
                response = json.loads(raw_response)

                if response.get("status") == "SUCCESS":
                    all_files = response.get("files", [])
                    # exclude files this peer already holds itself
                    already_held = {self.file_name} if self.file_content is not None else set()
                    available = [f for f in all_files if f not in already_held]
                    return available
                else:
                    return []
        except Exception as e:
            print(f"[-] Error listing files from server: {e}")
            return []


def run_as_holder(peer):
    # this peer holds the file: keep it alive so it can keep answering chunk requests
    print("[*] This peer holds the file and will stay online to serve chunk requests.")
    listener_thread = threading.Thread(target=peer.start_listening)
    listener_thread.daemon = True
    listener_thread.start()
    listener_thread.join()  # blocks here forever, keeping the process alive


def choose_file(available_files):
    print("[*] Files available to download:")
    for i, fname in enumerate(available_files):
        print(f"    {i + 1}. {fname}")

    while True:
        choice = input("Choose a file number to download: ")
        if choice.isdigit() and 1 <= int(choice) <= len(available_files):
            return available_files[int(choice) - 1]
        print(f"[!] Invalid choice, please enter a valid option")


def download_file(peer, chosen_file):
    peers, file_size = peer.request_file(chosen_file)
    
    if not peers:
        print("[!] Could not find any peers for this file — aborting download.")
        return

    allocation = peer.calculate_allocation(peers, file_size=file_size)
    print("[*] Allocation:")
    for (ip, port), info in allocation.items():
        start, end = info["range"]
        print(f"    {ip}:{port}  bandwidth={info['bandwidth']}  ->  bytes {start}-{end - 1}")

    chunks_with_ranges = []
    for (ip, port), info in allocation.items():
        chunk_data = peer.request_chunk(ip, port, info["range"])
        if chunk_data is not None:
            chunks_with_ranges.append((info["range"][0], info["range"][1], chunk_data))
        else:
            print(f"[!] Peer {ip}:{port} did not respond — its part will be missing")

    peer.reassemble(chunks_with_ranges, "downloaded_file.txt")
    print("[+] Download complete! Saved as downloaded_file.txt")


def run_as_target(peer):
    # this peer doesn't hold the file: offer to download
    available_files = peer.list_available_files()
    if not available_files:
        print("[!] No files available to download.")
        return

    chosen_file = choose_file(available_files)
    download_file(peer, chosen_file)


def main():
    print("Welcome to ParallelPulse!")
    print("Registering with server...")
    peer = Peer()
    peer.register_to_server()

    if peer.file_content is not None:
        run_as_holder(peer)
    else:
        run_as_target(peer)


if __name__ == "__main__":
    main()
