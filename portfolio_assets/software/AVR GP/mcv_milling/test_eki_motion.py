"""
EKI Robot Controller GUI — Rubex Spray v18.0
Tkinter GUI to connect, view live status, and move the robot.
Run: python test_eki_motion.py
"""
import socket as _sock
import time, threading
import tkinter as tk
from tkinter import messagebox

# ═══════════════════════════════════════════════════════════════
#  EkiClient — same protocol as v18
# ═══════════════════════════════════════════════════════════════
class EkiClient:
    SEP=","; TERM=";"
    def __init__(self, ip, port):
        self.ip=ip; self.port=port
        self._sock=None; self.connected=False
        self.robot_type=""; self.robot_name=""; self.sw_version=""
    @staticmethod
    def _is_float(s):
        try: float(s); return True
        except: return False
    def _cmd(self, cmd, args=None):
        if not self._sock: raise ConnectionError("Not connected")
        msg=cmd
        if args: msg+=self.SEP+self.SEP.join(str(a) for a in args)
        msg+=self.TERM
        self._sock.sendall(msg.encode('utf-8'))
        resp=b""
        while self.TERM.encode('utf-8') not in resp:
            chunk=self._sock.recv(4096)
            if not chunk: break
            resp+=chunk
        return resp.decode('utf-8').rstrip(self.TERM).strip()
    def connect(self):
        self._sock=_sock.socket(_sock.AF_INET,_sock.SOCK_STREAM)
        self._sock.settimeout(10.0)
        self._sock.connect((self.ip,self.port)); self.connected=True
        try: self.robot_name=self._cmd("getrobotname")
        except: self.robot_name="?"
        try:
            r=self._cmd("getrobottype"); p=r.split(',')
            v=p[1] if len(p)>1 else p[0]
            try: self.robot_type=v[v.index('#')+1:v.index('C4')]
            except: self.robot_type=v.strip()
        except: self.robot_type="?"
        try:
            r=self._cmd("getsoftwareversion"); p=r.split(',')
            v=p[1] if len(p)>1 else p[0]
            try: self.sw_version=v[v.index('V')+1:v.index('(')]
            except: self.sw_version=v.strip()
        except: self.sw_version="?"
        return True
    def disconnect(self):
        if self._sock:
            try: self._sock.close()
            except: pass
        self._sock=None; self.connected=False
    def _val(self, cmd):
        r=self._cmd(cmd); p=r.split(',')
        return p[1].strip() if len(p)>1 else p[0].strip()
    def _floats(self, cmd):
        raw=self._cmd(cmd).split(',')
        return [float(v) for v in raw if self._is_float(v)]
    def get_override(self):     return self._val("getoverride")
    def get_op_mode(self):      return self._val("getoperatingmode")
    def is_home(self):          return "true" in self._cmd("ishome").lower()
    def get_program_info(self):
        r=self._cmd("getprograminfo"); p=r.split(',')
        if len(p)>=3: return f"{p[1].strip()} ({p[2].strip()})"
        return p[0].strip()
    def get_joints(self):       return self._floats("getcurrentjoints")
    def get_pos(self):          return self._floats("getcurrentpos")
    def get_base(self):         return self._floats("getbasedata")
    def get_tool(self):         return self._floats("gettooldata")
    def get_load(self):
        raw=self._cmd("getloaddata").split(',')
        fl=[v for v in raw if self._is_float(v)]
        if len(fl)>=10: return f"M:{fl[0]}  CM:{','.join(fl[1:7])}  I:{','.join(fl[7:10])}"
        return ','.join(fl)
    def get_serial(self):       return self._val("getrobotserialnum")
    def get_num_axes(self):     return self._val("getnumrobotaxes")
    def get_num_ext(self):      return self._val("getnumexternalaxes")
    def get_abs_accur(self):    return self._val("getabsaccurstatus")
    def goto_joint_pos(self, joints):
        args=[f'{float(v):.4f}' for v in joints]
        return self._cmd("gotojointpos", args)
    def goto_frame(self, xyzabc):
        args=[f'{float(v):.4f}' for v in xyzabc]
        return self._cmd("gotoframe", args)
    def goto_cart_pos(self, pos):
        args=[f'{float(v):.4f}' for v in pos]
        return self._cmd("gotocartpos", args)


# ═══════════════════════════════════════════════════════════════
#  GUI CONTROLLER
# ═══════════════════════════════════════════════════════════════
BG  = "#0e0e1a"
BG2 = "#14142a"
BG3 = "#1a1a3a"
FG  = "#eeeef4"
FG2 = "#aabbcc"
GRN = "#00cc66"
RED = "#ff3355"
ORG = "#ff6600"
YEL = "#ffcc00"
CYN = "#44bbff"
FNT = "Segoe UI"
MNO = "Consolas"


class ControllerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("EKI Robot Controller — Rubex Spray v18.0")
        self.geometry("920x820")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(800, 700)

        self.eki = None
        self._poll_active = False

        self._build_gui()
        self.log("EKI Robot Controller ready. Enter IP and click Connect.")

    # ── BUILD GUI ──
    def _build_gui(self):
        # ── TOP: Connection bar ──
        conn = tk.Frame(self, bg=BG2, padx=10, pady=8)
        conn.pack(fill=tk.X, padx=6, pady=(6,2))

        tk.Label(conn, text="IP:", bg=BG2, fg=FG2, font=(FNT,10)).pack(side=tk.LEFT)
        self._ip = tk.Entry(conn, width=15, font=(MNO,11), bg=BG3, fg=FG,
                            insertbackground=FG, relief=tk.FLAT)
        self._ip.insert(0, "192.168.1.1")
        self._ip.pack(side=tk.LEFT, padx=(4,8))

        tk.Label(conn, text="Port:", bg=BG2, fg=FG2, font=(FNT,10)).pack(side=tk.LEFT)
        self._port = tk.Entry(conn, width=6, font=(MNO,11), bg=BG3, fg=FG,
                              insertbackground=FG, relief=tk.FLAT)
        self._port.insert(0, "54610")
        self._port.pack(side=tk.LEFT, padx=(4,12))

        self._btn_conn = tk.Button(conn, text="  Connect  ", bg="#1a6633", fg="white",
                                   font=(FNT,10,"bold"), relief=tk.FLAT, command=self._connect)
        self._btn_conn.pack(side=tk.LEFT, padx=2)

        self._btn_disc = tk.Button(conn, text="  Disconnect  ", bg="#661a1a", fg="white",
                                   font=(FNT,10,"bold"), relief=tk.FLAT, command=self._disconnect,
                                   state=tk.DISABLED)
        self._btn_disc.pack(side=tk.LEFT, padx=2)

        self._conn_lbl = tk.Label(conn, text="  ⬤ Disconnected", bg=BG2, fg=RED,
                                  font=(FNT,10,"bold"))
        self._conn_lbl.pack(side=tk.RIGHT, padx=8)

        # ── MIDDLE: Two columns ──
        mid = tk.Frame(self, bg=BG)
        mid.pack(fill=tk.BOTH, expand=True, padx=6, pady=4)

        # LEFT: Robot Status
        left = tk.Frame(mid, bg=BG2, padx=8, pady=6)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,3))

        hdr = tk.Frame(left, bg=BG2)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="ROBOT STATUS", bg=BG2, fg=ORG, font=(FNT,11,"bold")).pack(side=tk.LEFT)
        self._btn_update = tk.Button(hdr, text=" Update ", bg="#333366", fg=FG,
                                     font=(FNT,9,"bold"), relief=tk.FLAT,
                                     command=self._update_status, state=tk.DISABLED)
        self._btn_update.pack(side=tk.RIGHT, padx=2)
        self._btn_poll = tk.Button(hdr, text=" Live Poll ", bg="#444400", fg=YEL,
                                   font=(FNT,9,"bold"), relief=tk.FLAT,
                                   command=self._toggle_poll, state=tk.DISABLED)
        self._btn_poll.pack(side=tk.RIGHT, padx=2)

        tk.Frame(left, bg=ORG, height=2).pack(fill=tk.X, pady=(4,6))

        # Status rows
        self._sv = {}
        status_fields = [
            ("Robot Name",    "name",     GRN),
            ("Robot Type",    "type",     GRN),
            ("Serial",        "serial",   FG2),
            ("SW Version",    "version",  FG2),
            ("Axes",          "axes",     FG2),
            ("Ext Axes",      "ext",      FG2),
            ("Override %",    "override", YEL),
            ("Mode",          "mode",     YEL),
            ("At Home?",      "home",     CYN),
            ("Program",       "program",  FG2),
            ("Abs Accuracy",  "accur",    FG2),
        ]
        for label, key, color in status_fields:
            self._sv[key] = self._info_row(left, label, color)

        tk.Frame(left, bg="#333355", height=1).pack(fill=tk.X, pady=6)
        tk.Label(left, text="POSITION", bg=BG2, fg=CYN, font=(FNT,10,"bold")).pack(anchor="w")
        tk.Frame(left, bg=CYN, height=1).pack(fill=tk.X, pady=(2,4))

        pos_fields = [
            ("Cart Pos",   "cart",   GRN),
            ("Joint Pos",  "joints", CYN),
            ("Base Data",  "base",   FG2),
            ("Tool Data",  "tool",   FG2),
            ("Load Data",  "load",   FG2),
        ]
        for label, key, color in pos_fields:
            self._sv[key] = self._info_row(left, label, color)

        # RIGHT: Move Commands
        right = tk.Frame(mid, bg=BG2, padx=8, pady=6)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(3,0))

        tk.Label(right, text="MOVE COMMANDS", bg=BG2, fg=ORG, font=(FNT,11,"bold")).pack(anchor="w")
        tk.Frame(right, bg=ORG, height=2).pack(fill=tk.X, pady=(4,8))

        # Frame Move (XYZ ABC)
        tk.Label(right, text="Go To Frame (XYZABC):", bg=BG2, fg=FG, font=(FNT,9,"bold")).pack(anchor="w")
        gf = tk.Frame(right, bg=BG2)
        gf.pack(fill=tk.X, pady=4)

        self._mv = {}
        for i, (lbl, val) in enumerate([("X","500"),("Y","0"),("Z","800"),
                                         ("A","0"),("B","90"),("C","0")]):
            col = i % 3
            row = i // 3
            f = tk.Frame(gf, bg=BG2)
            if row == 0 and col == 0: f.pack(side=tk.TOP, fill=tk.X)
            tk.Label(gf if i < 3 else gf, text=f"{lbl}:", bg=BG2, fg=FG2, font=(FNT,9))

        # Redo with grid
        for w in gf.winfo_children(): w.destroy()
        for i, (lbl, val) in enumerate([("X","500"),("Y","0"),("Z","800"),
                                         ("A","0"),("B","90"),("C","0")]):
            r, c = i // 3, i % 3
            tk.Label(gf, text=f"{lbl}:", bg=BG2, fg=FG2, font=(MNO,10)).grid(row=r, column=c*2, sticky="e", padx=(6,2))
            e = tk.Entry(gf, width=10, font=(MNO,11), bg=BG3, fg=YEL,
                         insertbackground=FG, relief=tk.FLAT)
            e.insert(0, val)
            e.grid(row=r, column=c*2+1, padx=(0,8), pady=3)
            self._mv[lbl] = e

        self._btn_goto = tk.Button(right, text="  MOVE TO FRAME  ", bg="#1a5533", fg="white",
                                   font=(FNT,11,"bold"), relief=tk.FLAT,
                                   command=self._move_frame, state=tk.DISABLED)
        self._btn_goto.pack(fill=tk.X, pady=(6,4))

        # Read current pos into fields
        self._btn_read = tk.Button(right, text="  Read Current Pos Into Fields  ", bg="#333366",
                                   fg=FG, font=(FNT,9), relief=tk.FLAT,
                                   command=self._read_pos_into_fields, state=tk.DISABLED)
        self._btn_read.pack(fill=tk.X, pady=(0,8))

        tk.Frame(right, bg="#333355", height=1).pack(fill=tk.X, pady=6)

        # Joint Move (Home)
        tk.Label(right, text="Home Position (Joints):", bg=BG2, fg=FG, font=(FNT,9,"bold")).pack(anchor="w")
        hf = tk.Frame(right, bg=BG2)
        hf.pack(fill=tk.X, pady=4)

        self._jv = {}
        for i, (lbl, val) in enumerate([("A1","5"),("A2","-90"),("A3","100"),
                                         ("A4","5"),("A5","-10"),("A6","-5")]):
            r, c = i // 3, i % 3
            tk.Label(hf, text=f"{lbl}:", bg=BG2, fg=FG2, font=(MNO,10)).grid(row=r, column=c*2, sticky="e", padx=(6,2))
            e = tk.Entry(hf, width=8, font=(MNO,11), bg=BG3, fg=CYN,
                         insertbackground=FG, relief=tk.FLAT)
            e.insert(0, val)
            e.grid(row=r, column=c*2+1, padx=(0,8), pady=3)
            self._jv[lbl] = e

        self._btn_home = tk.Button(right, text="  GO HOME (PTP)  ", bg="#553311", fg="white",
                                   font=(FNT,11,"bold"), relief=tk.FLAT,
                                   command=self._move_home, state=tk.DISABLED)
        self._btn_home.pack(fill=tk.X, pady=(6,4))

        # Read current joints into fields
        self._btn_readj = tk.Button(right, text="  Read Current Joints Into Fields  ", bg="#333366",
                                    fg=FG, font=(FNT,9), relief=tk.FLAT,
                                    command=self._read_joints_into_fields, state=tk.DISABLED)
        self._btn_readj.pack(fill=tk.X, pady=(0,8))

        # ── BOTTOM: Log ──
        tk.Frame(right, bg="#333355", height=1).pack(fill=tk.X, pady=6)
        tk.Label(right, text="RESPONSE LOG:", bg=BG2, fg=FG2, font=(FNT,8)).pack(anchor="w")
        self._resp = tk.Label(right, text="-", bg=BG3, fg=GRN, font=(MNO,9),
                              anchor="w", justify=tk.LEFT, wraplength=400, padx=6, pady=4)
        self._resp.pack(fill=tk.X, pady=2)

        logf = tk.Frame(self, bg=BG)
        logf.pack(fill=tk.X, padx=6, pady=(0,6))
        tk.Label(logf, text="LOG:", bg=BG, fg=FG2, font=(FNT,8)).pack(anchor="w")
        self._log = tk.Text(logf, height=8, bg="#060610", fg=GRN, font=(MNO,9),
                            relief=tk.FLAT, insertbackground=FG, wrap=tk.WORD)
        self._log.pack(fill=tk.X)
        sb = tk.Scrollbar(self._log, command=self._log.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._log.config(yscrollcommand=sb.set)

    def _info_row(self, parent, label, color):
        row = tk.Frame(parent, bg=BG2)
        row.pack(fill=tk.X, pady=1)
        tk.Label(row, text=label, bg=BG2, fg=FG2, font=(FNT,9), width=14, anchor="w").pack(side=tk.LEFT)
        sv = tk.StringVar(value="-")
        tk.Label(row, textvariable=sv, bg=BG2, fg=color, font=(MNO,9),
                 anchor="w", justify=tk.LEFT, wraplength=380).pack(side=tk.LEFT, fill=tk.X, expand=True)
        return sv

    def log(self, msg):
        ts = time.strftime("%H:%M:%S")
        self._log.insert(tk.END, f"[{ts}] {msg}\n")
        self._log.see(tk.END)

    def _set_buttons(self, connected):
        st = tk.NORMAL if connected else tk.DISABLED
        self._btn_disc.config(state=st)
        self._btn_update.config(state=st)
        self._btn_poll.config(state=st)
        self._btn_goto.config(state=st)
        self._btn_home.config(state=st)
        self._btn_read.config(state=st)
        self._btn_readj.config(state=st)
        self._btn_conn.config(state=tk.DISABLED if connected else tk.NORMAL)

    # ── CONNECT / DISCONNECT ──
    def _connect(self):
        ip = self._ip.get().strip()
        port = int(self._port.get().strip())
        self.log(f"Connecting to {ip}:{port}...")
        self._conn_lbl.config(text="  ⬤ Connecting...", fg=YEL)
        self.update()
        try:
            self.eki = EkiClient(ip, port)
            self.eki.connect()
            self._conn_lbl.config(text=f"  ⬤ {self.eki.robot_name} | {self.eki.robot_type}", fg=GRN)
            self._set_buttons(True)
            self.log(f"Connected: {self.eki.robot_name} | {self.eki.robot_type} | SW {self.eki.sw_version}")
            self._update_status()
        except Exception as e:
            self._conn_lbl.config(text=f"  ⬤ Failed: {e}", fg=RED)
            self.log(f"Connection FAILED: {e}")
            self._set_buttons(False)

    def _disconnect(self):
        self._poll_active = False
        if self.eki:
            self.eki.disconnect()
        self._conn_lbl.config(text="  ⬤ Disconnected", fg=RED)
        self._set_buttons(False)
        for sv in self._sv.values(): sv.set("-")
        self.log("Disconnected.")

    # ── UPDATE STATUS ──
    def _update_status(self):
        if not self.eki or not self.eki.connected: return
        try:
            self._sv["name"].set(self.eki.robot_name)
            self._sv["type"].set(self.eki.robot_type)
            self._sv["version"].set(self.eki.sw_version)
        except: pass
        cmds = [
            ("serial",   self.eki.get_serial),
            ("axes",     self.eki.get_num_axes),
            ("ext",      self.eki.get_num_ext),
            ("override", self.eki.get_override),
            ("mode",     self.eki.get_op_mode),
            ("home",     lambda: str(self.eki.is_home())),
            ("program",  self.eki.get_program_info),
            ("accur",    self.eki.get_abs_accur),
        ]
        for key, fn in cmds:
            try: self._sv[key].set(str(fn()))
            except Exception as e: self._sv[key].set(f"ERR: {e}")
        # Position data
        try:
            p = self.eki.get_pos()
            self._sv["cart"].set(self._fmt_xyzabc(p))
        except Exception as e: self._sv["cart"].set(f"ERR: {e}")
        try:
            j = self.eki.get_joints()
            self._sv["joints"].set(self._fmt_joints(j))
        except Exception as e: self._sv["joints"].set(f"ERR: {e}")
        try:
            b = self.eki.get_base()
            self._sv["base"].set(self._fmt_xyzabc(b))
        except Exception as e: self._sv["base"].set(f"ERR: {e}")
        try:
            t = self.eki.get_tool()
            self._sv["tool"].set(self._fmt_xyzabc(t))
        except Exception as e: self._sv["tool"].set(f"ERR: {e}")
        try:
            self._sv["load"].set(str(self.eki.get_load()))
        except Exception as e: self._sv["load"].set(f"ERR: {e}")
        self.log("Status updated.")

    # ── LIVE POLLING ──
    def _toggle_poll(self):
        if self._poll_active:
            self._poll_active = False
            self._btn_poll.config(text=" Live Poll ", bg="#444400", fg=YEL)
            self.log("Live polling stopped.")
        else:
            self._poll_active = True
            self._btn_poll.config(text=" STOP Poll ", bg="#660000", fg=RED)
            self.log("Live polling started (1s interval)...")
            self._do_poll()

    def _do_poll(self):
        if not self._poll_active: return
        if not self.eki or not self.eki.connected:
            self._poll_active = False
            return
        try:
            ovr = self.eki.get_override()
            mode = self.eki.get_op_mode()
            home = str(self.eki.is_home())
            self._sv["override"].set(ovr)
            self._sv["mode"].set(mode)
            self._sv["home"].set(home)

            p = self.eki.get_pos()
            self._sv["cart"].set(self._fmt_xyzabc(p))
            j = self.eki.get_joints()
            self._sv["joints"].set(self._fmt_joints(j))
        except: pass
        self.after(1000, self._do_poll)

    # ── MOVE COMMANDS ──
    def _move_frame(self):
        if not self.eki or not self.eki.connected:
            messagebox.showinfo("", "Connect first."); return
        try:
            vals = [float(self._mv[k].get()) for k in ["X","Y","Z","A","B","C"]]
        except ValueError:
            messagebox.showerror("", "Invalid XYZ ABC values."); return
        self.log(f"MOVE FRAME: X:{vals[0]:.1f} Y:{vals[1]:.1f} Z:{vals[2]:.1f} A:{vals[3]:.1f} B:{vals[4]:.1f} C:{vals[5]:.1f}")
        try:
            resp = self.eki.goto_frame(vals)
            self._resp.config(text=f"gotoframe -> {resp}", fg=GRN)
            self.log(f"  Response: {resp}")
        except Exception as e:
            self._resp.config(text=f"ERROR: {e}", fg=RED)
            self.log(f"  ERROR: {e}")

    def _move_home(self):
        if not self.eki or not self.eki.connected:
            messagebox.showinfo("", "Connect first."); return
        try:
            vals = [float(self._jv[k].get()) for k in ["A1","A2","A3","A4","A5","A6"]]
            vals += [0, 0, 0, 0, 0, 0]  # E1-E6
        except ValueError:
            messagebox.showerror("", "Invalid joint values."); return
        self.log(f"GO HOME PTP: {' '.join(f'{v:.1f}' for v in vals[:6])}")
        try:
            resp = self.eki.goto_joint_pos(vals)
            self._resp.config(text=f"gotojointpos -> {resp}", fg=GRN)
            self.log(f"  Response: {resp}")
        except Exception as e:
            self._resp.config(text=f"ERROR: {e}", fg=RED)
            self.log(f"  ERROR: {e}")

    # ── READ POS INTO FIELDS ──
    def _read_pos_into_fields(self):
        if not self.eki or not self.eki.connected: return
        try:
            p = self.eki.get_pos()
            labels = ["X","Y","Z","A","B","C"]
            for i, lbl in enumerate(labels):
                if i < len(p):
                    self._mv[lbl].delete(0, tk.END)
                    self._mv[lbl].insert(0, f"{p[i]:.2f}")
            self.log(f"Read current pos into move fields: {self._fmt_xyzabc(p)}")
        except Exception as e:
            self.log(f"Error reading pos: {e}")

    def _read_joints_into_fields(self):
        if not self.eki or not self.eki.connected: return
        try:
            j = self.eki.get_joints()
            labels = ["A1","A2","A3","A4","A5","A6"]
            for i, lbl in enumerate(labels):
                if i < len(j):
                    self._jv[lbl].delete(0, tk.END)
                    self._jv[lbl].insert(0, f"{j[i]:.2f}")
            self.log(f"Read current joints into fields: {self._fmt_joints(j)}")
        except Exception as e:
            self.log(f"Error reading joints: {e}")

    # ── FORMATTERS ──
    @staticmethod
    def _fmt_xyzabc(vals):
        labels = ["X","Y","Z","A","B","C"]
        parts = []
        for i, v in enumerate(vals):
            lbl = labels[i] if i < 6 else f"E{i-5}"
            parts.append(f"{lbl}:{v:.2f}")
        return "  ".join(parts)

    @staticmethod
    def _fmt_joints(vals):
        ax = ["A1","A2","A3","A4","A5","A6"]
        main = "  ".join(f"{ax[i]}:{v:.2f}" for i, v in enumerate(vals[:6]))
        ext = vals[6:] if len(vals) > 6 else []
        if ext and any(v != 0 for v in ext):
            ext_str = "  ".join(f"E{i+1}:{v:.2f}" for i, v in enumerate(ext))
            return f"{main}  |  {ext_str}"
        return main


if __name__ == "__main__":
    app = ControllerApp()
    app.mainloop()
