import socket
import threading
import os
import json
import random

# requests
ID_C = "id"
SHARE_C = "share"
INFO_C = "info"
REC_C = "rec"
DISC_C = "disc"

# responses
DISC_SUC = "ds"
SHARE_SUC = "ss"
FILE_ERR = "fe"
AUTH_ERR = "ae"
REC_SUC = "rs"
SIZE_C = "size"

# commands
EXIT_C = "q"
GET_C = "get"
SHARE_C = "share"
LOGSREQ_C = "logs request"

TRACKER_PORT = 6771
LOCAL_IP = '127.0.0.1'

loglock = threading.Lock()

share_sockets = []
threads = []

def writelog(text):
    with loglock:
        with open(LOG_FN, "a") as f:
            f.write(text + "\n")

def req_id():
    global org_sock
    org_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    org_sock.bind((LOCAL_IP, 0))
    org_sock.sendto(ID_C.encode(), (LOCAL_IP, TRACKER_PORT))
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
    os.remove(LOG_FN)
    print(f"you're no longer a peer, goodbye {id}!")

def disconnect(id):
    org_sock.settimeout(1.0)
    org_sock.sendto(f"{DISC_C} {id}".encode(), (LOCAL_IP, TRACKER_PORT))
    try:
        resp = org_sock.recvfrom(1024).decode()
        if resp.split()[0] == DISC_SUC:
            exit_seq()
            return 0
        print(f"[error] {resp}")
        return -1
    except socket.timeout:
        exit_seq()
        return 0
    except:
        exit_seq()
        return 0

def sharefile(filename, new_sock):
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

def getseeders(filename, sock, trac_addr):
    sock.sendto(f"{INFO_C} {id} {filename}".encode(), trac_addr)
    m = sock.recv(1024).decode()
    if m == AUTH_ERR:
        writelog(f"request file {filename}: invalid id {id}")
        print("[error] invalid id")
        return None
    if m == FILE_ERR:
        writelog(f"request file {filename}: no seeder found")
        print("[error] there are no seeders for this file")
        return None
    seederslist = json.loads(m)
    writelog(f"request file {filename}: seeders {seederslist}")
    i = random.randint(0, len(seederslist)-1)
    seeder = eval(seederslist[i])
    return (seeder[0], int(seeder[1]))

def getfile(filename, lis_port, trac_addr):
    info_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    info_sock.bind((LOCAL_IP, 0))
    seeder = getseeders(filename, info_sock, trac_addr)
    info_sock.close()
    if not seeder:
        return
    get_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    get_sock.bind((LOCAL_IP, lis_port))
    get_sock.connect(seeder)
    writelog(f"request file {filename}: selected seeder {seeder}")
    print("getting file from", seeder)
    sm = get_sock.recv(1024).decode().split()
    if sm[0] == SIZE_C:
        size = int(sm[1])
        writelog(f"request file {filename}: file size {sm[1]}")
        print("file size:", size)
        transfered = 0
        with open(f"{DOWNLOAD_DIR}/{filename}", "wb") as f:
            while transfered < size:
                data = get_sock.recv(1024)
                transfered += len(data)
                f.write(data)
        get_sock.close()
        writelog(f"request file {filename}: file download complete at {DOWNLOAD_DIR}/{filename}")
        print("file download complete")
        print(f"find it at {DOWNLOAD_DIR}/{filename}")
        # become a seeder
        new_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        new_sock.bind((LOCAL_IP, 0))
        share_sockets.append(new_sock)
        org_sock.sendto(f"{REC_C} {id} {new_sock.getsockname()[1]} {filename}".encode(), trac_addr)
        resp = org_sock.recv(1024).decode()
        if resp == REC_SUC:
            t = threading.Thread(target=sharefile, args=(filename, new_sock))
            threads.append(t)
            t.start()
            writelog(f"{id} is now a seeder for file {filename}, listening address {new_sock.getsockname()}")
        else:
            writelog(f"{id} failed to reshare file {filename}")
            print(f"[error] {resp}")
    else:
        writelog(f"request file {filename}: failed to get file")
        print("[error] failed to get file")


id = req_id()

global DOWNLOAD_DIR
global LOG_FN
DOWNLOAD_DIR = f"downloads_{id}"
LOG_FN = f"log{id}.txt"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
open(LOG_FN, "w").close()

while True:
    command = input()
    type = command.split()[0]
    if type == EXIT_C:
        if disconnect(id) == 0:
            break
    elif type == GET_C:
        _, lis_port, trac_addr, filename = command.split()
        ip, port = trac_addr.split(':')
        t = threading.Thread(target=getfile, args=(filename, int(lis_port), (ip, int(port))))
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
                writelog(f"{id} failed to share file {file}: connection to tracker {trac_addr} failed")
                print(f"[error] connection to tacker {trac_addr} failed")
                continue
            resp = org_sock.recvfrom(1024)
            if resp[0].decode() == SHARE_SUC:
                new_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                new_sock.bind((LOCAL_IP, int(lis_port)))
                share_sockets.append(new_sock)
                t = threading.Thread(target=sharefile, args=(file, new_sock))
                threads.append(t)
                t.start()
                writelog(f"{id} shared file {file} successfully, tracker address {trac_addr}, listening port {lis_port}")
                print(f"file {file} shared successfully!")
            else:
                print(f"[error] {resp[0].decode()}")
    elif command == LOGSREQ_C:
        with loglock:
            with open(LOG_FN, "r") as f:
                for l in f:
                    print(l, end="")
    else:
        print("[error] invalid command")