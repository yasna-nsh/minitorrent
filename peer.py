import socket

# requests
ID_C = "id"
SHARE_C = "share"
INFO_C = "info"
GET_C = "get"
DISC_C = "disc"

# responses
DISC_SUC = "ds"

# commands
EXIT_C = "q"
GET_C = "get"
SHARE_C = "share"
TRACKER_PORT = 6771

def req_id():
    global org_sock
    org_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    org_sock.bind(("127.0.0.1", 0))
    org_sock.sendto(ID_C.encode(), ("127.0.0.1", TRACKER_PORT))
    p = org_sock.recvfrom(1024)
    id = p[0].decode()
    print(f"you're a peer now! your ID is {id}")
    return id

def disconnect(id):
    org_sock.sendto(f"{DISC_C} {id}".encode(), ("127.0.0.1", TRACKER_PORT))
    p = org_sock.recvfrom(1024)
    if p[0].decode() == DISC_SUC:
        org_sock.close()
        print(f"you're no longer a peer, goodbye {id}!")
        return 0
    print(f"[error] {p[0].decode()}")
    return -1


id = req_id()

while True:
    command = input()
    type = command.split()[0]
    if type == EXIT_C:
        if disconnect(id) == 0:
            break
    elif type == GET_C:
        pass
    elif type == SHARE_C:
        pass
    else:
        print("[error] invalid command")