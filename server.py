import socket
import json
import threading

SERVER_IP = '127.0.0.1'
SERVER_PORT = 5000

BASE_PORT = 8001
port_counter = 0

DUMMY_FILE_NAME = "project_demo.txt"
DUMMY_FILE_CONTENT = "0123456789"

# peers_table: (ip, port) -> {bandwidth, file_name}
# in this POC there is only one file, but in the real project there will be a file list
peers_table = {}

def start_server():
    """
    starting the main server and listens to connections in port 5000
    """
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((SERVER_IP, SERVER_PORT))
    server_socket.listen(10)
    
    print(f"[*] Central Server running on {SERVER_IP}:{SERVER_PORT}...")
    
    while True:
        client_sock, addr = server_socket.accept()
        # new thread for every request for not blocking other peers
        client_handler = threading.Thread(target=handle_client, args=(client_sock, addr))
        client_handler.daemon = True
        client_handler.start()

def handle_client(client_socket, client_address):
    """
    used to handle requests and navigate them to their asked action.
    """
    try:
        raw_data = client_socket.recv(4096).decode('utf-8')
        if not raw_data:
            return

        data = json.loads(raw_data)
        action = data.get("action")

        if action == "CONNECT":
            handle_register(client_socket, client_address)
        elif action == "QUERY":
            handle_query(client_socket, data)
        elif action == "LIST_FILES": 
            handle_list_files(client_socket)
        else:
            response = {"status": "ERROR", "message": "Unknown action"}
            client_socket.sendall(json.dumps(response).encode('utf-8'))

    except Exception as e:
        print(f"[-] Error handling client {client_address}: {e}")
    finally:
        client_socket.close()


def handle_register(client_socket, client_address):
    """
    Handles register requests (action == CONNECT)
    """
    global port_counter

    bandwidth_list = [50,30,20,10,5] # the first will get 50, second 30...
    assigned_port = BASE_PORT + port_counter
    if port_counter < 4:
        file_payload = DUMMY_FILE_CONTENT
    else:
        file_payload = None
    assigned_bandwidth = bandwidth_list[port_counter]
    port_counter +=1

    response = {
        "status" : "SUCCESS",
        "assigned_port" : assigned_port,
        "bandwidth" : assigned_bandwidth,
        "file" : file_payload,
        "file_name" : DUMMY_FILE_NAME
    }

    print(f"[+] Registered Peer #{port_counter} | Port: {assigned_port} | Bandwidth: {assigned_bandwidth} Mbps | Has Chunks: {file_payload is not None}")

    peer_ip = SERVER_IP  # all peers run on localhost for this POC
    peers_table[(peer_ip, assigned_port)] = {
        "bandwidth": assigned_bandwidth,
        "file_name": DUMMY_FILE_NAME if file_payload is not None else None
    }
    client_socket.sendall(json.dumps(response).encode('utf-8'))


def handle_query(client_socket, request_data):
    """
    handles action == QUERY
    """
    requested_file = request_data.get("file_name")
    print(f"[*] Query received for file: '{requested_file}'")

    matching_peers = [
        {"ip": ip, "port": port, "bandwidth": info["bandwidth"]}
        for (ip, port), info in peers_table.items()
        if info["file_name"] == requested_file
    ]

    response = {
        "status": "SUCCESS",
        "file_name": requested_file,
        "peers": matching_peers,
        "file_size": len(DUMMY_FILE_CONTENT)
    }

    client_socket.sendall(json.dumps(response).encode('utf-8'))


def handle_list_files(client_socket):
    # returns all distinct file names currently held by at least one registered peer
    available_files = list({
        info["file_name"] for info in peers_table.values()
        if info["file_name"] is not None
    })
    response = {"status": "SUCCESS", "files": available_files}
    client_socket.sendall(json.dumps(response).encode('utf-8'))


if __name__ == "__main__":
    start_server()