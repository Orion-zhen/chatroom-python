import sys
import time
import json
import socket
import random
import logging
import threading
import filechunkio
from cmd import Cmd
from config.server_config import IP, PORT


logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)


class Client(Cmd):
    def __init__(self):
        super().__init__()
        self.to_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.buffer = 2048
        self.username = None
        self.password = None
        self.logged_in = False
        self.ftp_host = None

    def start(self):
        # server_ip = input("Input server ip: ")
        # server_port = input("Input server port: ")
        # try:
            # self.to_server.connect((server_ip, int(server_port)))
            self.to_server.connect((IP, PORT))
            self.cmdloop()
        # except:
        #     logging.error("Failed to connect to server")

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
                buffer = self.to_server.recv(self.buffer).decode()
                body = json.loads(buffer)
                
                if body["type"] == "approval":
                    if not self.ftp_host:
                        print("得到响应")
                        self.send_file(body["content"])
                        self.ftp_host.close()
                        self.ftp_host = None
                    else:
                        print(body["content"])
                
                elif body["type"] == "denial":
                    if not self.ftp_host:
                        self.ftp_host.close()
                        
                    print(body["content"])

                elif body["type"] == "chat":
                    print(f"{body['from']}: {body['content']}")
                elif body["type"] == "broadcast":
                    print(f"[Broadcast] {body['from']}: {body['content']}")

                elif body["type"] == "ftp_request":
                    # 收到ftp请求, 连接到对方开启的端口
                    print(f"[FTP] {body['from']}: {body['content']}")
                    decision = input("Receive it?[Y/n]: ").lower()[0]
                    self.decide_ftp(decision, body)
                elif body["type"] == "ftp_replay":
                    pass

            except Exception:
                logging.error("Cannot receive message from server")
                break

    def do_login(self, args=None):
        username = input("Enter your username: ")
        password = input("Enter your password: ")
        self.send_to_server(
            json.dumps(
                {"type": "login", "username": username, "password": password}
            )
        )
        try:
            buffer = self.to_server.recv(self.buffer).decode()
            body = json.loads(buffer)
            if body["type"] == "approval":
                # 服务器接受登录
                self.username = username
                self.password = password
                self.logged_in = True
                print("Login success!")

                thread = threading.Thread(target=self.receive_from_server, daemon=True)
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
            )
        )
        
        try:
            buffer = self.to_server.recv(self.buffer).decode()
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

        thread = threading.Thread(target=self.send_to_server, args=(message,), daemon=True)
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

        thread = threading.Thread(target=self.send_to_server, args=(message,), daemon=True)
        thread.start()

    def do_ftp(self, args):
        args = args.split(" ")
        target_name = args[0]
        file_name = args[1]
        ftp_port = self.get_available_port()
        print("获得可用端口")
        self.ftp_host = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ftp_host.bind(("0.0.0.0", ftp_port))
        
        message = json.dumps(
            {
                "type": "ftp_request",
                "from": self.username,
                "to": target_name,
                "ip": str(socket.gethostbyname(socket.gethostname())),
                "port": ftp_port,
                "content": file_name
            }
        )
        print("发送请求")
        self.send_to_server(message)
        print("等待响应")
        
        self.ftp_host.listen()

    def do_logout(self, args=None):
        message = json.dumps({"type": "logout", "username": self.username})
        thread = threading.Thread(target=self.send_to_server, args=(message,), daemon=True)
        thread.start()
        self.logged_in = False
        self.to_server.close()
        print("Logout success!")
        sys.exit(0)
        
    def get_available_port(self):
        while True:
            port = random.randint(10000, 65535)  # 选择一个在self.buffer到65535范围内的端口，这个范围是未注册端口，可以自由使用
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.bind(('localhost', port))  # 尝试绑定到这个端口
                sock.close()  # 如果成功，关闭socket
                return port  # 返回这个可用的端口
            except socket.error as e:
                # 如果端口已被使用，捕获异常并继续循环
                pass
    
    def decide_ftp(self, decision: str, body: dict):
        """根据参数决定是否接受FTP连接, 是则开始接收文件

        Args:
            decision (str): 决定选项
            body (dict): FTP请求报文
        """
        target_name = body['from']
        target_ip = body['ip']
        target_port = body['port']
        file_name = body['content']
        if decision != 'y':
            # 否决FTP连接, 通过服务器送到发起方
            message = json.dumps(
                {
                    "type": "denial",
                    "from": self.username,
                    "to": target_name,
                    "content": "FTP refused"
                }
            )
            
            self.send_to_server(message)

        else:
            # 发送同意报文, 让发送方开始发送文件
            message = json.dumps(
                {
                    "type": "approval",
                    "from": self.username,
                    "to": target_name,
                    "content": file_name
                }
            )
            self.send_to_server(message)
            
            time.sleep(3) # 睡一会儿, 防止发送方还没开始listen
            
            # 连接到请求报文中给出的地址, 开始接收文件
            print("发起连接")
            receiver = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            receiver.connect((target_ip, target_port))
            with filechunkio.open(file_name, 'rb') as f:
                while True:
                    chunk = receiver.recv(self.buffer)
                    if not chunk:
                        break
                    f.write(chunk)
            
            print(f"Successfully received file {file_name} from {target_name}")
            receiver.close()
    
    def send_file(self, file_name: str):
        receiver_socket, _ = self.ftp_host.accept()
        print("收到连接")
        with filechunkio.open(file_name, "rb") as f:
            while True:
                chunk = f.read(self.buffer)
                if not chunk:
                    break
                receiver_socket.send(chunk)
        receiver_socket.close()