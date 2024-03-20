import json
import socket
import logging
import threading
from cmd import Cmd


logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)


class Client(Cmd):
    def __init__(self):
        super.__init__()
        self.to_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.username = None
        self.password = None
        self.logged_in = False

    def send_to_server(self, message):
        """将消息发送到服务器

        Args:
            message (str): 已经json化的字符串
        """
        self.to_server.send(message.encode())

    def receive_from_server(self):
        """从服务器接收消息"""
        while self.logged_in:
            try:
                buffer = self.to_server.recv(1024).decode()
                body = json.loads(buffer)

                if body["type"] == "approval":
                    print(body["content"])
                elif body["type"] == "denial":
                    print(body["content"])

                elif body["type"] == "chat":
                    print(f"{body['from']}: {body['content']}")
                elif body["type"] == "broadcast":
                    print(f"[Broadcast] {body['from']}: {body['content']}")

                elif body["type"] == "ftp_request":
                    pass
                elif body["type"] == "ftp_replay":
                    pass

                elif body["type"] == "voice":
                    pass

            except Exception:
                logging.error("Cannot receive message from server")

    def do_login(self, args=None):
        username = input("Enter your username: ")
        password = input("Enter your password: ")
        self.send_to_server(
            json.dumps(
                {"type": "login", "username": username, "password": password}
            ).encode()
        )
        try:
            buffer = self.to_server.recv(1024).decode()
            body = json.loads(buffer)
            if body["type"] == "approval":
                # 服务器接受登录
                self.username = username
                self.password = password
                self.logged_in = True
                print("Login success!")

                thread = threading.Thread(target=self.receive_from_server)
                thread.setDaemon(True)
                thread.start()
            else:
                print(body["content"])

        except Exception:
            logging.error("Cannot receive message from server")

    def do_signup(self, args=None):
        username = input("Enter your username: ")
        password = input("Enter your password: ")
        self.send_to_server(
            json.dumps(
                {"type": "signup", "username": username, "password": password}
            ).encode()
        )
        
        try:
            buffer = self.to_server.recv(1024).decode()
            body = json.loads(buffer)
            if body["type"] == "approval":
                # 服务器接受登录
                self.username = username
                self.password = password
                self.logged_in = True
                print("Signup success!")
            else:
                print(body["content"])
        except Exception:
            logging.error("Cannot receive message from server")
    
    def do_chat(self, args):
        args = args.split(" ")
        target_name = args[0]
        content = " ".join(args[1:])
        message = json.dumps(
            {
                "type": "chat",
                "from": self.username,
                "to": target_name,
                "content": content,
            }
        )

        thread = threading.Thread(target=self.send_to_server, args=(message,))
        thread.setDaemon(True)
        thread.start()

    def do_broadcast(self, args):
        content = args
        message = json.dumps(
            {
                "type": "broadcast",
                "from": self.username,
                "content": content,
            }
        )

        thread = threading.Thread(target=self.send_to_server, args=(message,))
        thread.setDaemon(True)
        thread.start()

    def do_logout(self, args=None):
        message = json.dumps({"type": "logout", "username": self.username})
        thread = threading.Thread(target=self.send_to_server, args=(message,))
        thread.setDaemon(True)
        thread.start()
        self.logged_in = False
        self.to_server.close()
        print("Logout success!")
