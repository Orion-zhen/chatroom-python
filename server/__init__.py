import os
import json
import random
import socket
import logging
import threading
import pyaudio
import vidstream
from config.server_config import IP, PORT1, PORT2
from server.database import get_user, add_user
from config.audio_config import CHUNK, FORMAT, CHANNELS, RATE


logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)

class Server:
    def __init__(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM) #数据、文件传输TCP套接字
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) 

        self.buffer = 2048

        self.active_dict = {}
        """活动中的用户字典
        active_list = {
            "<username>": {
                "socket": socket,
                "ip": ip,
                "port": port,
            },
        }
        """

        self.message_queue = {}
        """消息队列
        message_queue = {
            "<username>": [
                {
                    "type": "chat",
                    "from": "<selfname>",
                    "content": "<content>"
                },
                {
                    "type": "chat",
                    "from": "<selfname>",
                    "content": "<content>"
                },
            ]
        }
        """

    def braodcast(self, username="system", message=""):
        """广播消息

        Args:
            username (str, optional): 发送广播消息的用户名称. Defaults to "system".
            message (str, optional): 广播的消息内容. Defaults to "".
        """
        for target_name in self.active_dict.keys():
            if target_name != username:
                # 不对自己广播
                target_socket = self.active_dict[target_name]["socket"]
                target_socket.send(
                    json.dumps(
                        {"type": "broadcast", "from": username, "content": message}
                    ).encode()
                )
    """ def audio_chat(self, target_name):
        #接受来自客户端端数据包
        try:
            while True:
                packet, client_address = self.audio_server.recvfrom(CHUNK + 50)
                data = packet[:CHUNK]
                target_name = packet[CHUNK:].decode().strip('\x00')
                target_ip = self.active_dict[target_name]["ip"]
                
                ####FIX HERE####

                target_port = 0 #port????
                
                ####FIX HERE####

                target_address = (target_ip, target_port)
                self.audio_server.sendto(data, target_address)
        except KeyboardInterrupt:
            print("服务器语音服务结束") """
        

    def user_thread(self, active_name):
        """专门接收该用户消息并进行处理的线程
        可以进行的操作有: 私聊, 广播, 传输文件, 语音聊天

        Args:
            active_name (str): 一个在线的用户名, 对应self.active_list中的一个键
        """
        while True:
            # try:
                print("尝试用户线程读取消息")
                buffer = (
                    self.active_dict[active_name]["socket"].recv(self.buffer).decode()
                )
                body = json.loads(buffer)

                if body["type"] == "logout":
                    logging.info(f"[User] {active_name} 退出登陆")
                    # 用户退出时关闭连接, 然后从active_list中删除该用户
                    self.active_dict[active_name]["socket"].close()
                    self.active_dict.pop(active_name)
                    # 结束该用户线程
                    break

                elif body["type"] == "broadcast":
                    logging.info(f"[User] {active_name} 广播消息: {body['content']}")
                    self.braodcast(active_name, body["content"])

                elif body["type"] == "audio":
                    logging.info(f"[User] {active_name} ->(audio) {body['to']}")
                    target_name = body["to"]
                    if target_name in self.active_dict.keys():
                        # 如果目标用户在活动列表中, 则发送语音消息
                        target_socket = self.active_dict[target_name]["socket"]
                        sender_name = body["from"]
                        sender_ip = body["ip"]
                        sender_port = body["audio_port"]
                        message = json.dumps(
                            {
                                "type": "audio",
                                "from": sender_name,
                                "to": target_name,
                                "ip": sender_ip,
                                "audio_port": sender_port
                            }
                        )
                        target_socket.send(message.encode())
                    else:
                        # 如果目标用户不在活动列表中，则发起语音失败
                        print("发起语音失败")

                else:
                    logging.info(f"[User] {active_name} -> {body['to']}")
                    target_name = body["to"]
                    if target_name in self.active_dict.keys():
                        # 如果目标用户在活动列表中, 则发送消息
                        target_socket = self.active_dict[target_name]["socket"]
                        target_socket.send(buffer.encode())
                    elif body["type"] == "ftp_request":
                        # 离线文件, 暂存至对应文件夹中
                        print("暂存离线文件")
                        sender_ip = body["ip"]
                        sender_port = body["port"]
                        file_name = body["content"]
                        receiver = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        receiver.connect((sender_ip, sender_port))
                        if not os.path.exists(
                            os.path.join(
                                os.path.dirname(__file__), f"cache/{target_name}"
                            )
                        ):
                            os.makedirs(
                                os.path.join(
                                    os.path.dirname(__file__), f"cache/{target_name}"
                                )
                            )
                        with open(
                            os.path.join(
                                os.path.dirname(__file__),
                                f"cache/{target_name}",
                                file_name,
                            ),
                            "wb",
                        ) as f:
                            while True:
                                data = receiver.recv(1024)
                                if not data:
                                    break
                                f.write(data)
                        self.message_queue.setdefault(target_name, [])
                        self.message_queue[target_name].append(body)
                        print(self.message_queue[target_name])
                    else:
                        print("暂存消息")
                        # 如果目标用户不在活动列表中, 则暂存消息
                        self.message_queue.setdefault(target_name, [])
                        self.message_queue[target_name].append(body)
                        print(self.message_queue[target_name])

            # except Exception:
            #     logging.error(
            #         f"连接失效: {self.active_dict[active_name]['socket'].getsockname()}, {self.active_dict[active_name]['socket'].fileno()}"
            #     )
            #     self.active_dict[active_name]["socket"].close()
            #     self.active_dict.pop(active_name)

    def wait_for_login(self, active_socket, addr):
        """对于服务器端接收到的连接, 进入等待登录函数, 等待该连接的发起方发送登录或注册信息

        Args:
            active_socket (socket.socket): 收到的连接
            addr (tuple(ip, port)): 连接来源
        """
        print("进入等待登陆线程")
        try:
            print("尝试接收消息")
            buffer = active_socket.recv(self.buffer).decode()
            body = json.loads(buffer)
            print("接收消息成功")
            if body["type"] == "login":
                data_base_info = get_user(body["username"])
                if data_base_info != None and body["password"] == data_base_info[1]:
                    print("密码正确")
                    # 数据库中有并且密码正确
                    activer = {
                        "socket": active_socket,
                        "ip": addr[0],
                        "port": addr[1],
                    }
                    self.active_dict.setdefault(body["username"], {})
                    self.active_dict[body["username"]] = activer
                    print("已添加到活跃列表")
                    active_socket.send(
                        json.dumps(
                            {
                                "type": "approval",
                                "content": f"{body['username']} is logged in",
                            }
                        ).encode()
                    )

                    # 在登录成功后检查离线消息
                    print("检查离线消息")
                    if body["username"] in self.message_queue:
                        for msg in self.message_queue[body["username"]]:
                            if msg["type"] == "chat":
                                print(msg)
                                active_socket.send(json.dumps(msg).encode())
                            elif msg["type"].startswith("ftp"):
                                # 待实现: 离线文件传输
                                file_path = os.path.join(
                                    os.path.dirname(__file__),
                                    f"cache/{msg['to']}",
                                    msg["content"],
                                )
                                file_name = msg["content"]
                                ftp_port = self.get_available_port()
                                ftp_tmp_socket = socket.socket(
                                    socket.AF_INET, socket.SOCK_STREAM
                                )
                                ftp_tmp_socket.bind(("0.0.0.0", ftp_port))

                                ftp_req = json.dumps(
                                    {
                                        "type": "ftp_request",
                                        "from": msg["from"],
                                        "to": msg["to"],
                                        "ip": str(
                                            socket.gethostbyname(socket.gethostname())
                                        ),
                                        "port": ftp_port,
                                        "content": file_name,
                                    }
                                )
                                active_socket.send(ftp_req.encode())
                                ftp_tmp_socket.listen()
                                receiver_socket, _ = ftp_tmp_socket.accept()
                                with open(file_path, "rb") as f:
                                    while True:
                                        chunk = f.read(self.buffer)
                                        if not chunk:
                                            break
                                        receiver_socket.send(chunk)
                                receiver_socket.close()
                                ftp_tmp_socket.close()
                        # 删除已读消息
                        del self.message_queue[body["username"]]

                    # 开启用户线程
                    thread = threading.Thread(
                        target=self.user_thread, args=(body["username"],), daemon=True
                    )
                    thread.start()
                    print("成功激活用户线程")
                    print(f"当前用户列表: {self.active_dict.keys()}")
                else:
                    print("拒绝登陆")
                    active_socket.send(
                        json.dumps(
                            {"type": "denial", "content": "login failed"}
                        ).encode()
                    )

            elif body["type"] == "signup":
                print("注册请求")
                print("搜索数据库")
                data_base_info = get_user(body["username"])
                print(f"数据库返回结果: {data_base_info}")
                if data_base_info == None:
                    print("数据库中没有该用户名, 注册之")
                    # 数据库中没有该用户名, 则注册之
                    add_user(body["username"], body["password"])
                    active_socket.send(
                        json.dumps(
                            {"type": "approval", "content": "signup success"}
                        ).encode()
                    )

                    # 添加到活跃列表
                    activer = {
                        "socket": active_socket,
                        "ip": addr[0],
                        "port": addr[1],
                    }
                    self.active_dict.setdefault(body["username"], activer)
                    # 开启用户线程
                    thread = threading.Thread(
                        target=self.user_thread, args=(body["username"],), daemon=True
                    )
                    thread.start()
                    print("成功激活用户线程")
                else:
                    # 有, 则返回用户名冲突
                    active_socket.send(
                        json.dumps(
                            {"type": "denial", "content": "username already exists"}
                        ).encode()
                    )

        except Exception:
            logging.error(
                f"无法连接: {active_socket.getsockname()}, {active_socket.fileno()}"
            )
            active_socket.close()

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

    def start(self):
        """服务器, 启动!"""
        logging.info(f"绑定地址 {IP}:{PORT1}")
        self.server.bind((IP, PORT1))
        logging.info(f"启动服务器")
        self.server.listen(10)

        # 初始化连接
        self.active_dict.clear()
        self.message_queue.clear()

        # 开始监听
        while True:
            try:
                connection, addr = self.server.accept()
                logging.info(f"连接来自 {addr[0]}:{addr[1]}")
                # 开启新线程
                thread = threading.Thread(
                    target=self.wait_for_login, args=(connection, addr), daemon=True
                )
                thread.start()

            except Exception:
                logging.error(
                    f"连接异常: {connection.getsockname()}, {connection.fileno()}"
                )
                connection.close()
