import socket
import threading
import os
import json

# requests
ID_C = "id"
SHARE_C = "share"
INFO_C = "info"
DISC_C = "disc"

# responses
DISC_SUC = "ds"
SHARE_SUC = "ss"
FILE_ERR = "fe"

#  commands
EXIT_C = "q"

# log names
IDS_LOG_FN = f"ids{os.getpid()}.txt"
FILES_LOG_FN = f"files{os.getpid()}.txt"

# error codes
IDADDRNM = -1 # peer's address doesn't match id
IDNF = -2 # id not found

# error messages
IDADDRNM_M = "authentication failed, address doesn't match id"
IDNF_M = "invalid id"
NOTUNIQUE_M = "file name not unique"
UNEXP_M = "unexpected error"

ids_lock = threading.Lock()
files_lock = threading.Lock()
threads = []

def getfreeid():
    with ids_lock:
        with open(IDS_LOG_FN, "r") as f:
            max = 0
            for l in f:
                cur = int(l.split()[0][1:])
                if cur > max:
                    max = cur
            return f"u{max + 1}"
    return -1
    
def allocid(id, addr):
    with ids_lock:
        with open(IDS_LOG_FN, "a") as f:
            f.write(f"{id} {addr}\n")
            return id
    return -1

def remove_peer(id, reqaddr):
    lines = []
    found = False
    with ids_lock:
        with open(IDS_LOG_FN, "r") as f:
            for l in f:
                curid, addr = l.split(maxsplit=1)
                if curid == id:
                    found = True
                    if eval(addr) != reqaddr:
                        return IDADDRNM
                else:
                    lines.append(l)
        if not found:
            return IDNF
        with open(IDS_LOG_FN, "w") as f:
            f.writelines(lines)
    flines = []
    with files_lock:
        with open(FILES_LOG_FN, "r") as f:
            for l in f:
                curid, addr, curfn = l.split('|', maxsplit=2)
                if curid != id:
                    flines.append(l)
        with open(FILES_LOG_FN, "w") as f:
            f.writelines(flines)        
    return 0

def isvalididaddr(id, reqaddr):
    with ids_lock:
        with open(IDS_LOG_FN, "r") as f:
            for l in f:
                curid, addr = l.split(maxsplit=1)
                if curid == id:
                    if eval(addr) != reqaddr:
                        return IDADDRNM
                    return 0
    return IDNF

def isfilenameunique(filename):
    with files_lock:
        with open(FILES_LOG_FN, "r") as f:
            for l in f:
                _, _, curfn = l.split('|', maxsplit=2)
                if ''.join(curfn.split()) == ''.join(filename.split()):
                    return -1
    return 0

def addfile(id, lis_addr, file):
    with files_lock:
        with open(FILES_LOG_FN, "a") as f:
            f.write(f"{id}|{lis_addr}|{file}\n")

def getlist(filename):
    list = []
    with files_lock:
        with open(FILES_LOG_FN, "r") as f:
            for l in f:
                id, lis_addr, curfn = l.split('|', maxsplit=2)
                if ''.join(curfn.split()) == ''.join(filename.split()):
                    list.append(lis_addr)
            return list
    return None

def process_req(r, s):
    command = r[0].decode().split()[0]
    if command == ID_C:
        id = getfreeid()
        if id == -1:
            print("[error] id allocation failed")
        elif allocid(id, r[1]) == -1:
            print("[error] peer addition failed")
        else:
            s.sendto(id.encode(), r[1])
    elif command == SHARE_C:
        _, id, lis_port, file = r[0].decode().split()
        val = isvalididaddr(id, r[1])
        if val == IDNF:
            s.sendto(IDNF_M.encode(), r[1])
        elif val == IDADDRNM:
            s.sendto(IDADDRNM.encode(), r[1])
        elif val == 0:
            if isfilenameunique(file) != 0:
                s.sendto(NOTUNIQUE_M.encode(), r[1])
            else:
                addfile(id, (r[1][0], lis_port), file)
                s.sendto(SHARE_SUC.encode(), r[1])
    elif command == INFO_C:
        list = getlist(r[0].decode().split(maxsplit=1)[1])
        if not list:
            s.sendto(FILE_ERR.encode(), r[1])
        else:
            s.sendto(json.dumps(list).encode(), r[1])
    elif command == DISC_C:
        id = r[0].decode().split()[1]
        res = remove_peer(id, r[1])
        if res == IDNF:
            s.sendto(IDNF_M.encode(), r[1])
        elif res == IDADDRNM:
            s.sendto(IDADDRNM_M.encode(), r[1])
        elif res == 0:
            s.sendto(DISC_SUC.encode(), r[1])
        else:
            s.sendto(UNEXP_M.encode(), r[1])
    else:
        s.sendto(f"invalid request {r[0].decode()}".encode(), r[1])

def handle_requests(ip, port):
    global sock
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((ip, int(port)))
    sock.settimeout(1.0)
    while True:
        try:
            req = sock.recvfrom(1024)
            t = threading.Thread(target=process_req, args=(req, sock))
            threads.append(t)
            t.start()
        except socket.timeout:
            continue
        except:
            break

def handle_cmd():
    while True:
        command = input()
        type = command.split()[0]
        if type == EXIT_C:
            os.remove(IDS_LOG_FN)
            os.remove(FILES_LOG_FN)
            sock.close()
            for t in threads:
                t.join()
            print("tracker disconnected")
            return
        else:
            print("[error] invalid command")

ip, port = input().split(':')
open(IDS_LOG_FN, "w").close()
open(FILES_LOG_FN, "w").close()

t = threading.Thread(target=handle_requests, args=(ip, port))
threads.append(t)
t.start()
handle_cmd()