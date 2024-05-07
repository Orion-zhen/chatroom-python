import os
import sys
import time
import json
import socket
import random
import logging
import threading
import filechunkio
import pyaudio
import vidstream
from cmd import Cmd
from config.server_config import IP, PORT
from config.audio_config import CHUNK, FORMAT, CHANNELS, RATE

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
        self.audio_sender = None
        self.audio_receiver = None

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

    """ def audio_start(self, target_name):
        将语音消息发送到服务器

        Args:
            message (str): 已经json化的字符串
        
        # 创建音频流
        audio = pyaudio.PyAudio()
        stream = audio.open(format=FORMAT, channels=CHANNELS,
                            rate=RATE, input=True, output=True,
                            frames_per_buffer=CHUNK)
        try:
            while True:
                # 从麦克风读取音频数据
                data = stream.read(CHUNK)

                # 发送音频数据到服务器
                packet = data + target_name.encode()
                #packet = data
                self.audio.sendto(packet, (IP, PORT2))

                # 接收来自其他客户端的音频数据
                data, addr = self.audio.recvfrom(CHUNK * 2)
                #buffer = self.to_server_audio.recv(self.buffer).decode()
                #body = json.loads(buffer)

                # 播放音频数据
                stream.write(data)
        except KeyboardInterrupt:
            print("语音聊天结束")
            stream.stop_stream()
            stream.close()
            audio.terminate() """
    
    def print_content(self, content):
        length = len(content)
        i = 0
        while i < length:
            if content[i] == '\\':
                if i != length - 1:
                    if content[i + 1] == 'n':
                        i += 1
                        print('\n', end='')
                else:
                    print(content[i])
            else:
                print(content[i], end='')
            i += 1
        print('\n')

    def receive_from_server(self):
        """从服务器接收消息"""
        while self.logged_in:
            # try:
            buffer = self.to_server.recv(self.buffer).decode()
            body = json.loads(buffer)

            # if body["type"] == "approval":
            # if not self.ftp_host:
            # print("得到响应")
            # self.send_file(body["content"])
            # self.ftp_host.close()
            # self.ftp_host = None
            # else:
            #     print(body["content"])

            if body["type"] == "denial":
                if not self.ftp_host:
                    self.ftp_host.close()

                print(body["content"])

            elif body["type"] == "chat":
                print(body['from'], end=":\n") 
                self.print_content(body['content'])
            elif body["type"] == "broadcast":
                print(f"[Broadcast] {body['from']}:")
                self.print_content(body['content'])
            elif body["type"] == "audio_request":
                print(f"[Audio] {body['from']}")
                #local_ip = socket.gethostbyname(socket.gethostname())
                local_ip = '192.168.1.114'
                #audio_port = self.get_available_port()
                audio_port = 7070
                message = json.dumps(
                    {
                        "type": "audio_response",
                        "from": self.username,
                        "to": body["from"],
                        "audio_port": audio_port,
                        "ip": local_ip,
                    }
                )
                self.send_to_server(message)
                try:
                    self.audio_receiver = vidstream.AudioReceiver(local_ip, audio_port)
                    self.audio_sender = vidstream.AudioSender(
                        str(body["ip"]), int(body["audio_port"])
                    )
                    threading.Thread(
                        target=self.audio_receiver.start_server, daemon=True
                    ).start()
                    threading.Thread(
                        target=self.audio_sender.start_stream, daemon=True
                    ).start()
                    
                except:
                    print("开启错误")
            elif body["type"] == "audio_response":
                self.audio_sender = vidstream.AudioSender(
                    body["ip"], body["audio_port"]
                )
                threading.Thread(
                    target=self.audio_sender.start_stream, daemon=True
                ).start()
            elif body["type"] == "ftp_request":
                # 收到ftp请求, 连接到对方开启的端口
                print(f"[FTP] {body['from']}: {body['content']}")
                target_ip = body["ip"]
                target_port = body["port"]
                file_name = body["content"]
                print("发起连接")
                try:
                    receiver = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    receiver.connect((target_ip, target_port))
                except:
                    print("连接失败")
                if not os.path.exists(os.path.join(os.path.dirname(__file__), "recv/")):
                    os.makedirs(os.path.join(os.path.dirname(__file__), "recv/"))
                with open(
                    os.path.join(
                        os.path.join(os.path.dirname(__file__), "recv/"), file_name
                    ),
                    "wb",
                ) as f:
                    while True:
                        chunk = receiver.recv(self.buffer)
                        if not chunk:
                            break
                        f.write(chunk)

                print(f"Successfully received file {file_name} from {target_ip}")
                receiver.close()
            elif body["type"] == "ftp_replay":
                pass

        # except Exception:
        #     logging.error("Cannot receive message from server")
        #     # break

    def do_login(self, args=None):
        username = input("Enter your username: ")
        password = input("Enter your password: ")

        self.send_to_server(
            json.dumps({"type": "login", "username": username, "password": password})
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
            json.dumps({"type": "signup", "username": username, "password": password})
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
        thread = threading.Thread(
            target=self.send_to_server, args=(message,), daemon=True
        )
        thread.start()

    def do_audio(self, args):
        target_name = args
        #my_ip = socket.gethostbyname(socket.gethostname())
        #audio_port = self.get_available_port()
        my_ip = '192.168.1.114'
        audio_port = 7070
        message = json.dumps(
            {
                "type": "audio_request",
                "from": self.username,
                "to": target_name,
                "audio_port": audio_port,
                "ip": my_ip,
            }
        )
        self.send_to_server(message)
        self.audio_receiver = vidstream.AudioReceiver(my_ip, audio_port)
        receiver_thread = threading.Thread(
            target=self.audio_receiver.start_server, daemon=True
        )
        receiver_thread.start()

    def do_broadcast(self, args):
        content = args
        message = json.dumps(
            {
                "type": "broadcast",
                "from": self.username,
                "content": content,
            }
        )

        thread = threading.Thread(
            target=self.send_to_server, args=(message,), daemon=True
        )
        thread.start()

    def do_ftp(self, args):
        args = args.split(" ")
        target_name = args[0]
        file_path = args[1]
        file_name = os.path.basename(file_path)
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
                "content": file_name,
            }
        )
        print("发送请求")
        self.send_to_server(message)
        print("等待响应")

        self.ftp_host.listen()

        receiver_socket, _ = self.ftp_host.accept()
        print("收到连接")
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(self.buffer)
                if not chunk:
                    break
                receiver_socket.send(chunk)
        receiver_socket.close()

    def do_logout(self, args=None):
        message = json.dumps({"type": "logout", "username": self.username})
        thread = threading.Thread(
            target=self.send_to_server, args=(message,), daemon=True
        )
        thread.start()
        self.logged_in = False
        self.to_server.close()
        print("Logout success!")
        sys.exit(0)

    def get_available_port(self):
        while True:
            port = random.randint(
                10000, 65535
            )  # 选择一个在self.buffer到65535范围内的端口，这个范围是未注册端口，可以自由使用
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.bind(("localhost", port))  # 尝试绑定到这个端口
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
        target_name = body["from"]
        target_ip = body["ip"]
        target_port = body["port"]
        file_name = body["content"]
        if decision != "y":
            # 否决FTP连接, 通过服务器送到发起方
            message = json.dumps(
                {
                    "type": "denial",
                    "from": self.username,
                    "to": target_name,
                    "content": "FTP refused",
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
                    "content": file_name,
                }
            )
            self.send_to_server(message)

            time.sleep(3)  # 睡一会儿, 防止发送方还没开始listen

            # 连接到请求报文中给出的地址, 开始接收文件
            print("发起连接")
            receiver = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            receiver.connect((target_ip, target_port))
            with open(file_name, "rb") as f:
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
    
    