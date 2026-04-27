import socket
import time
import random

# ===============================
# VARPROXY CONNECTION
# ===============================
KUKA_IP = "192.168.1.10"
KUKA_PORT = 7000

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((KUKA_IP, KUKA_PORT))

def send(cmd):
    sock.sendall((cmd + "\n").encode())
    time.sleep(0.03)

def read():
    return sock.recv(1024).decode()

# ===============================
# GENERATE PATH ON PC
# ===============================
path_id = random.randint(1, 4)

path = []
for i in range(5):
    path.append((
        500 + i * 20,     # X
        40 * path_id,    # Y
        600,             # Z
        0, 90, 0,        # A B C
        6, 35            # S T
    ))

# ===============================
# SEND PATH
# ===============================
send(f"SET PathID {path_id}")

for i, p in enumerate(path, start=1):
    x,y,z,a,b,c,s,t = p
    send(
        f"SET Path[{i}] "
        f"{{X {x},Y {y},Z {z},A {a},B {b},C {c},S {s},T {t}}}"
    )

# ===============================
# TRIGGER EXECUTION
# ===============================
send("SET NewPathReady TRUE")

sock.close()
