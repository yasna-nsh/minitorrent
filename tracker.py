import socket
import threading
import os
import json
import shutil

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

#  commands
EXIT_C = "q"
LOGSREQ_C = "logs request"
ALLLOGS_C = "all-logs"
FLOGS_C = "file_logs"

# log names
pid = os.getpid()
IDS_LS_FN = f"ids{pid}.txt"
FILES_LS_FN = f"files{pid}.txt"
GEN_LOG_FN = f"genlog{pid}.txt"
FILE_LOG_DIR = f"filelogs{pid}"

# error codes
IDADDRNM = -1 # peer's address doesn't match id
IDNF = -2 # id not found

# error messages
IDADDRNM_M = "authentication failed, address doesn't match id"
IDNF_M = "invalid id"
NOTUNIQUE_M = "file name not unique"
UNIQUE_M = "file name unique"
UNEXP_M = "unexpected error"

ids_lock = threading.Lock()
files_lock = threading.Lock()
genlog_lock = threading.Lock()
threads = []
filelog_locks = {}

def writegenlog(text):
    with genlog_lock:
        with open(GEN_LOG_FN, "a") as f:
            f.write(text + "\n")

def writefilelog(filename, text):
    if filename not in filelog_locks:
        return
    with filelog_locks[filename]:
        with open(f"{FILE_LOG_DIR}/{filename}.txt", "a") as f:
            f.write(text + "\n")

def createfilelog(filename):
    filelog_locks[filename] = threading.Lock()
    open(f"{FILE_LOG_DIR}/{filename}.txt", "w").close()

def getfreeid():
    with ids_lock:
        with open(IDS_LS_FN, "r") as f:
            max = 0
            for l in f:
                cur = int(l.split()[0][1:])
                if cur > max:
                    max = cur
            return f"u{max + 1}"
    return -1
    
def allocid(id, addr):
    with ids_lock:
        with open(IDS_LS_FN, "a") as f:
            f.write(f"{id} {addr}\n")
            return id
    return -1

def remove_peer(id, reqaddr, removed_files):
    lines = []
    found = False
    with ids_lock:
        with open(IDS_LS_FN, "r") as f:
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
        with open(IDS_LS_FN, "w") as f:
            f.writelines(lines)
    flines = []
    with files_lock:
        with open(FILES_LS_FN, "r") as f:
            for l in f:
                curid, addr, curfn = l.split('|', maxsplit=2)
                if curid != id:
                    flines.append(l)
                else:
                    removed_files.append((addr, ''.join(curfn.split())))
        with open(FILES_LS_FN, "w") as f:
            f.writelines(flines)        
    return 0

def isvalididaddr(id, reqaddr):
    with ids_lock:
        with open(IDS_LS_FN, "r") as f:
            for l in f:
                curid, addr = l.split(maxsplit=1)
                if curid == id:
                    if eval(addr) != reqaddr:
                        return IDADDRNM
                    return 0
    return IDNF

def isfilenameunique(filename):
    with files_lock:
        with open(FILES_LS_FN, "r") as f:
            for l in f:
                _, _, curfn = l.split('|', maxsplit=2)
                if ''.join(curfn.split()) == ''.join(filename.split()):
                    return -1
    return 0

def addfile(id, lis_addr, file):
    with files_lock:
        with open(FILES_LS_FN, "a") as f:
            f.write(f"{id}|{lis_addr}|{file}\n")

def getlist(filename):
    list = []
    with files_lock:
        with open(FILES_LS_FN, "r") as f:
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
            writegenlog(f"[{id}] joined")
    elif command == SHARE_C or command == REC_C:
        type = "share" if command == SHARE_C else "reshare"
        _, id, lis_port, file = r[0].decode().split()
        val = isvalididaddr(id, r[1])
        if val == IDNF:
            s.sendto(IDNF_M.encode(), r[1])
            writegenlog(f"[{id}] {type} request with invalid id")
        elif val == IDADDRNM:
            s.sendto(IDADDRNM.encode(), r[1])
            writegenlog(f"[{id}] {type} request with non-matching id and address {r[1]}")
        elif val == 0:
            if command == SHARE_C:
                if isfilenameunique(file) != 0:
                    s.sendto(NOTUNIQUE_M.encode(), r[1])
                    writegenlog(f"[{id}] share file with non-unique name {file}")
                else:
                    addfile(id, (r[1][0], lis_port), file)
                    s.sendto(SHARE_SUC.encode(), r[1])
                    createfilelog(file)
                    writefilelog(file, f"shared id {id}, listening address {(r[1][0], lis_port)}")
                    writegenlog(f"[{id}] share file {file}, listening address {(r[1][0], lis_port)}")
            else:
                if isfilenameunique(file) == 0:
                    s.sendto(UNIQUE_M.encode(), r[1])
                    writegenlog(f"[{id}] reshare file with unique name {file}")
                else:
                    addfile(id, (r[1][0], lis_port), file)
                    s.sendto(REC_SUC.encode(), r[1])
                    writefilelog(file, f"shared id {id}, listening address {(r[1][0], lis_port)}")
                    writegenlog(f"[{id}] reshare file {file}, listening address {(r[1][0], lis_port)}")
    elif command == INFO_C:
        _, id, filename = r[0].decode().split(maxsplit=2)
        val = isvalididaddr(id, r[1])
        if val == IDNF:
            s.sendto(AUTH_ERR.encode(), r[1])
            writegenlog(f"[{id}] info request with invalid id for file {filename}")
        else:
            list = getlist(filename)
            if not list:
                writegenlog(f"[{id}] share request, no seeders found for file {filename}")
                s.sendto(FILE_ERR.encode(), r[1])
            else:
                writegenlog(f"[{id}] share request, list of seeders for file {filename}: {list}")
                s.sendto(json.dumps(list).encode(), r[1])
    elif command == DISC_C:
        id = r[0].decode().split()[1]
        removed_files = []
        res = remove_peer(id, r[1], removed_files)
        if res == IDNF:
            s.sendto(IDNF_M.encode(), r[1])
            writegenlog(f"[{id}] disconnect request with invaid id")
        elif res == IDADDRNM:
            s.sendto(IDADDRNM_M.encode(), r[1])
            writegenlog(f"[{id}] disconnect request with non-matching id and address {r[1]}")
        elif res == 0:
            s.sendto(DISC_SUC.encode(), r[1])
            writegenlog(f"[{id}] disconnected successfully, removed files: {removed_files}")
            for rf in removed_files:
                writefilelog(rf[1], f"{id} disconnected, removed listening address {r[1]}")
        else:
            s.sendto(UNEXP_M.encode(), r[1])
    else:
        s.sendto(f"invalid request {r[0].decode()}".encode(), r[1])
        writegenlog(f"[{id}] invalid request")

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

def printgenlog():
    with genlog_lock:
        with open(GEN_LOG_FN, "r") as f:
            for l in f:
                print(l, end="")

def printfilelog(fn):
    if fn not in filelog_locks:
        print("[error] invalid filename")
        return
    with filelog_locks[fn]:
        with open(f"{FILE_LOG_DIR}/{fn}.txt", "r") as f:
            for l in f:
                print(l, end="")

def handle_cmd():
    while True:
        command = input("> ")
        type = command.split()[0]
        if type == EXIT_C:
            os.remove(IDS_LS_FN)
            os.remove(FILES_LS_FN)
            os.remove(GEN_LOG_FN)
            shutil.rmtree(FILE_LOG_DIR, ignore_errors=True)
            sock.close()
            for t in threads:
                t.join()
            print("tracker disconnected")
            return
        elif command == LOGSREQ_C:
            printgenlog()
        elif command == ALLLOGS_C:
            for fn in filelog_locks:
                print(f"~~~ {fn} log ~~~")
                printfilelog(fn)
                print("~~~~~~")
        elif type == FLOGS_C:
            fn = command.split(maxsplit=1)[1]
            printfilelog(fn)
        else:
            print("[error] invalid command")


ip, port = input().split(':')
open(IDS_LS_FN, "w").close()
open(FILES_LS_FN, "w").close()
open(GEN_LOG_FN, "w").close()
os.makedirs(FILE_LOG_DIR, exist_ok=True)

t = threading.Thread(target=handle_requests, args=(ip, port))
threads.append(t)
t.start()
handle_cmd()