import socket
import threading
import os
import json
import random

# requests
ID_C = "id"
SHARE_C = "share"
INFO_C = "info"
DISC_C = "disc"

# responses
DISC_SUC = "ds"
SHARE_SUC = "ss"
FILE_ERR = "fe"
SIZE_C = "size"

# commands
EXIT_C = "q"
GET_C = "get"
SHARE_C = "share"
TRACKER_PORT = 6771

share_sockets = []
threads = []

def req_id():
    global org_sock
    org_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    org_sock.bind(("127.0.0.1", 0))
    org_sock.sendto(ID_C.encode(), ("127.0.0.1", TRACKER_PORT))
    p = org_sock.recvfrom(1024)
    id = p[0].decode()
    print(f"you're a peer now! your ID is {id}")
    return id

def exit_seq():
    org_sock.close()
    for s in share_sockets:
        s.close()
    for t in threads:
        t.join()
    print(f"you're no longer a peer, goodbye {id}!")

def disconnect(id):
    org_sock.sendto(f"{DISC_C} {id}".encode(), ("127.0.0.1", TRACKER_PORT))
    try:
        resp = org_sock.recvfrom(1024).decode()
        if resp.split()[0] == DISC_SUC:
            exit_seq()
            return 0
        print(f"[error] {resp}")
        return -1
    except:
        exit_seq()
        return 0

def sharefile(filename, lis_port):
    new_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    new_sock.bind(('127.0.0.1', lis_port))
    share_sockets.append(new_sock)
    new_sock.listen()
    new_sock.settimeout(1.0)
    while True:
        try:
            con, addr = new_sock.accept()
            size = os.path.getsize(filename)
            con.sendall(f"{SIZE_C} {size}".encode())
            with open(filename, "rb") as f:
                while True:
                    data = f.read(1024)
                    if not data:
                        break
                    con.sendall(data)
        except socket.timeout:
            continue
        except:
            new_sock.close()
            break

def getseeders(filename):
    org_sock.sendto(f"{INFO_C} {filename}".encode(), ("127.0.0.1", TRACKER_PORT))
    m = org_sock.recv(1024).decode()
    if m == FILE_ERR:
        return None
    seederslist = json.loads(m)
    i = random.randint(0, len(seederslist)-1)
    seeder = eval(seederslist[i])
    return (seeder[0], int(seeder[1]))

def getfile(filename, lis_addr):
    seeder = getseeders(filename)
    if not seeder:
        print("[error] there are no seeders for this file")
        return
    print("getting file from", lis_addr)
    get_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    get_sock.bind(('127.0.0.1', 0))
    get_sock.connect(lis_addr)
    sm = get_sock.recv(1024).decode().split()
    if sm[0] == SIZE_C:
        size = int(sm[1])
        transfered = 0
        with open(f"{DOWNLOAD_DIR}/{filename}", "w") as f:
            while transfered < size:
                data = get_sock.recv(1024).decode()
                transfered += len(data)
                f.write(data)
        get_sock.close()
        print("file downloaded successfully")
        # become a seeder
        t = threading.Thread(target=sharefile, args=(filename, 0))
        threads.append(t)
        t.start()
    else:
        print("[error] failed to get file")

id = req_id()
global DOWNLOAD_DIR
DOWNLOAD_DIR = f"downloads_{id}"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
while True:
    command = input()
    type = command.split()[0]
    if type == EXIT_C:
        if disconnect(id) == 0:
            break
    elif type == GET_C:
        filename = command.split()[1]
        t = threading.Thread(target=getfile, args=(filename,))
        threads.append(t)
        t.start()
    elif type == SHARE_C:
        _, lis_port, trac_addr, file = command.split()
        if not os.path.isfile(file):
            print(f"[error] invalid path {file}")
            continue
        else:
            ip, port = trac_addr.split(':')
            n = org_sock.sendto(f"{SHARE_C} {id} {lis_port} {file}".encode(), (ip, int(port)))
            if n == 0:
                print(f"[error] connection to tacker {trac_addr} failed")
                continue
            resp = org_sock.recvfrom(1024)
            if resp[0].decode() == SHARE_SUC:
                t = threading.Thread(target=sharefile, args=(file, int(lis_port)))
                threads.append(t)
                t.start()
                print(f"file {file} shared successfully!")
            else:
                print(f"[error] {resp[0].decode()}")
    else:
        print("[error] invalid command")