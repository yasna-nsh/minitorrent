import socket
import threading
import os

# requests
ID_C = "id"
SHARE_C = "share"
INFO_C = "info"
GET_C = "get"
DISC_C = "disc"

# responses
DISC_SUC = "ds"

#  commands
EXIT_C = "q"

# log names
IDS_LOG_FN = f"ids{os.getpid()}.txt"

# error codes
RP_NM = -1 # peer's address doesn't match id
RP_IDNF = -2 # id not found

lock = threading.Lock()
threads = []

def getfreeid():
    with lock:
        with open(IDS_LOG_FN, "r") as f:
            max = 0
            for l in f:
                cur = int(l.split()[0][1:])
                if cur > max:
                    max = cur
            return f"u{max + 1}"
    return -1
    
def allocid(id, addr):
    with lock:
        with open(IDS_LOG_FN, "a") as f:
            f.write(f"{id} {addr}")
            return id
    return -1

def remove_peer(id, reqaddr):
    lines = []
    found = False
    with lock:
        with open(IDS_LOG_FN, "r") as f:
            for l in f:
                curid, addr = l.split(maxsplit=1)
                if curid == id:
                    found = True
                    if eval(addr) != reqaddr:
                        return RP_NM
                else:
                    lines.append(l)
        if not found:
            return RP_IDNF
        with open(IDS_LOG_FN, "w") as f:
            f.writelines(lines)
    return 0
    

def process_req(r, s):
    command = r[0].decode().split()[0]
    if command == ID_C:
        id = getfreeid()
        if id == -1:
            print("[error] id allocation failed")
            return
        if allocid(id, r[1]) == -1:
            print("[error] peer addition failed")
            return
        s.sendto(id.encode(), r[1])
    elif command == SHARE_C:
        pass
    elif command == INFO_C:
        pass
    elif command == GET_C:
        pass
    elif command == DISC_C:
        id = r[0].decode().split()[1]
        res = remove_peer(id, r[1])
        if res == RP_IDNF:
            print("[error] invalid id")
        elif res == RP_NM:
            print("[error] authentication failed, address doesn't match id")
        elif res == 0:
            s.sendto(DISC_SUC.encode(), r[1])
        else:
            print(f"[error] invalid return value from remove_peer {res}")
    else:
        print(f"[error] invalid request {r[0].decode()} from {r[1]}")

def handle_requests(ip, port):
    global sock
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((ip, int(port)))

    while True:
        try:
            req = sock.recvfrom(1024)
            t = threading.Thread(target=process_req, args=(req, sock))
            threads.append(t)
            t.start()
        except:
            break

def handle_cmd():
    command = input()
    type = command.split()[0]
    if type == EXIT_C:
        os.remove(IDS_LOG_FN)
        sock.close()
        for t in threads:
            t.join()
        #TODO tell peers the tracker has left (is this necessary?)
        #TODO join threads
    else:
        print("[error] invalid command")


ip, port = input().split(':')
f = open(IDS_LOG_FN, "w")
f.close()
t = threading.Thread(target=handle_requests, args=(ip, port))
threads.append(t)
t.start()
handle_cmd()