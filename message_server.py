import os
import sys
import time
import ctypes
import datetime
import socket
import select
import threading
import socketserver
import subprocess

import tkinter
from tkinter import ttk

import collections

cMessageServer = os.path.abspath(r"message_server.py")

is_master_available = True

# Constants being used across classes.
# Should they be globals? Another class? Referenced by the others?
SEND_KEY = "?*knock*knock*?"
BUFFERSIZE = 4096 * 2

quiet_mode = False


class ThreadedTCPRequestHandler(socketserver.BaseRequestHandler):
    # collections.deque() is supposed to be threadsafe.
    collector = collections.deque()

    @staticmethod
    def get_timestamp():
        current_time = time.time()
        timestamp = datetime.datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S')
        return timestamp

    # Keep collecting messages -- and when a SEND_KEY is received, send all the stored data.
    def handle(self):
        data = str(self.request.recv(BUFFERSIZE), 'ascii')
        timestamp = self.get_timestamp()
        if len(data) > 0:
            if SEND_KEY in data:
                if len(self.collector) > 0:
                    newline = "{}: {}\r\n".format(timestamp, self.collector.pop())
                    self.request.sendall(bytes(newline, 'ascii'))

            else:
                self.collector.extend(data.splitlines())


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass


class GUI(tkinter.Tk):
    def __init__(self, server):
        self.jobs = list()
        self.server = server
        tkinter.Tk.__init__(self)

        N, S, E, W = tkinter.N, tkinter.S, tkinter.E, tkinter.W
        # setup the title of the app
        self.wm_title("Message Server")
        self.add_file_menu()
        #self.setup_app_icon()

        #Main UI Setup

        # setup the textbox
        self.text = tkinter.Text(self, width=85, height=16, borderwidth=1, wrap='none')

        # Add the binding
        self.text.bind("<Control-Key-a>", self.select_all)
        self.text.bind("<Control-Key-A>", self.select_all)  # just in case caps lock is on

        # setup the scrollbar
        self.scrollbar = ttk.Scrollbar(self, orient=tkinter.VERTICAL, command=self.text.yview)
        self.scrollbarH = ttk.Scrollbar(self, orient=tkinter.HORIZONTAL, command=self.text.xview)

        # associate the scrollbar to the textbox.
        self.text.config(yscrollcommand=self.scrollbar.set)
        self.text.config(xscrollcommand=self.scrollbarH.set)

        # bottom part of window
        ip, port = self.server.server_address
        self.label = ttk.Label(self,
                               text="Message Server started on: {}:{}".format(ip, port),
                               anchor=W,
                               background='#FFFACD')

        # Grid the widgets
        #self.frame.grid(column=1, row=1, rowspan=1, columnspan=3, sticky=(N, E, W, S))
        self.text.grid(column=1, row=2, rowspan=2, columnspan=3, sticky=(N, E, S, W))
        self.scrollbar.grid(column=2, row=2, rowspan=2, sticky=(N, S, E))
        self.scrollbarH.grid(column=1, row=3, columnspan=3, sticky=(S, E, W))
        ttk.Sizegrip().grid(column=2, row=4, sticky=(S, E))
        self.label.grid(column=1, row=4, columnspan=3, sticky=(N, E, W, S))

        # provide stickiness for different parts of the window.
        self.grid_rowconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=1)
        self.grid_rowconfigure(3, weight=1)

        self.after(0, self.callback_get_messages)

    def setup_app_icon(self):
        # setup the app icon
        head, tail = os.path.split(os.path.realpath(__file__))
        icon_path = os.path.join(head, 'icons', 'icon.ico')
        self.wm_iconbitmap(bitmap=icon_path)

    # setup loop to be called once mainloop starts.
    def callback_get_messages(self):
        #self.text.tag_add("error", "1.21", "1.28")

        messages = self.requestMessages(self.server)
        if messages is not None:
            lines = messages.splitlines()
            for line in lines:
                self.text.insert(1.0, "{}\n".format(line))
                if "ERROR" in line:
                    self.text.tag_add("error", "1.21", "1.28")
                    self.text.tag_config("error", background="red", foreground="blue")
                if (" "*200) in line:
                    self.text.tag_add("newline", "1.21", "1.251")
                    self.text.tag_config("newline", background="gray", foreground="blue")

        self.after(1, self.callback_get_messages)
        self.update_idletasks()

    def callback_set_clipboard(self):
        self.winSetClipboard(self.text)

    @staticmethod
    def winSetClipboard(text):
        GMEM_DDESHARE = 0x2000
        ctypes.windll.user32.OpenClipboard(0)
        ctypes.windll.user32.EmptyClipboard()
        try:
            # works on Python 2 (bytes() only takes one argument)
            hCd = ctypes.windll.kernel32.GlobalAlloc(GMEM_DDESHARE, len(bytes(text)) + 1)
        except TypeError:
            # works on Python 3 (bytes() requires an encoding)
            hCd = ctypes.windll.kernel32.GlobalAlloc(GMEM_DDESHARE, len(bytes(text, 'ascii')) + 1)
        pchData = ctypes.windll.kernel32.GlobalLock(hCd)
        try:
            # works on Python 2 (bytes() only takes one argument)
            ctypes.cdll.msvcrt.strcpy(ctypes.c_char_p(pchData), bytes(text))
        except TypeError:
            # works on Python 3 (bytes() requires an encoding)
            ctypes.cdll.msvcrt.strcpy(ctypes.c_char_p(pchData), bytes(text, 'ascii'))
        ctypes.windll.kernel32.GlobalUnlock(hCd)
        ctypes.windll.user32.SetClipboardData(1, hCd)
        ctypes.windll.user32.CloseClipboard()

    @staticmethod
    def requestMessages(server):
        data = None

        try:
            ip, port = server.server_address
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((ip, port))

            sock.settimeout(0.1)

            # ask server to send data.
            sock.sendall(bytes(SEND_KEY, 'ascii'))

            ready = select.select([sock], [], [], 0.1)
            if ready[0]:
                data = str(sock.recv(BUFFERSIZE), 'ascii')
            sock.close()

        except socket.timeout as e:
            print(e)

        except Exception as e:
            msg = "{}\n".format(e)
            print(msg)

        return data

    def clear_text_field(self):
        self.text.delete(1.0, tkinter.END)

    def add_file_menu(self):
        self.option_add('*tearOff', False)

        self.menubar = tkinter.Menu(self)
        self.filemenu = tkinter.Menu(self.menubar)
        self.filemenu.add_command(label="Clear All", command=self.clear_text_field)

        self.menubar.add_cascade(label="File", menu=self.filemenu)

        self.config(menu=self.menubar)

    # Select all the text in textbox
    def select_all(self, event):
        self.text.tag_add(tkinter.SEL, "1.0", tkinter.END)
        self.text.mark_set(tkinter.INSERT, "1.0")
        self.text.see(tkinter.INSERT)
        return 'break'

    def select_copy(self, event):
        self.clipboard_clear()
        self.clipboard_append(self.text)
        self.selection_get(selection="CLIPBOARD")


def start_server(HOST, PORT):
    """
    If PORT is set to zero - the server will select an arbitrary unused port
    """
    try:
        server = ThreadedTCPServer((HOST, PORT), ThreadedTCPRequestHandler)

        # Start a thread w/ server -- that thread will then start one more thread for each request
        server_thread = threading.Thread(target=server.serve_forever)

        # Exit the server thread when the main thread terminates
        server_thread.daemon = True
        server_thread.start()

        print("Server ({0}:{1}) loop running in thread: {2}".format(HOST, PORT, server_thread.name))

        return server
    except OSError as e:
        print(e)


# ----------------------------------------------------------------------------------------------------
# NORMAL USERS
# ----------------------------------------------------------------------------------------------------


def start_gui(message, HOST, PORT):
    server = start_server(HOST, PORT)
    if server is not None:
        gui = GUI(server)
        send_message(message)
        gui.mainloop()




def send_message(message):
    if message and quiet_mode is not True:
        ip, port = "localhost", 9001
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect((ip, port))
            sock.sendall(bytes(message, 'ascii'))
            response = str(sock.recv(BUFFERSIZE), 'ascii')

        except Exception as e:
            print("Error on {}:{} -> {}".format(ip, port, e))
            cmd = [cMessageServer, "Start up..."]
            process = subprocess.Popen(cmd,
                                       shell=True,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE,
                                       stdin=None,
                                       env=os.environ)
            time.sleep(2)  # Delay to allow server to spin up.
            send_message(str(message))

        finally:
            sock.close()

if __name__ == "__main__":
    sys.argv =["", "hello"]
    if len(sys.argv) > 1:
        HOST, PORT = "localhost", 9001
        start_gui("{0}\n{1}\n".format("_____________________________", "Message server started..."),
                  HOST,
                  PORT)
