import json
import socket
import logging
import threading
from config.server_config import IP, PORT
from server.database import get_user, add_user


logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO
)


class Server:
    def __init__(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

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

    def user_thread(self, active_name):
        """专门接收该用户消息并进行处理的线程
        可以进行的操作有: 私聊, 广播, 传输文件, 语音聊天

        Args:
            active_name (str): 一个在线的用户名, 对应self.active_list中的一个键
        """
        while True:
            try:
                buffer = self.active_dict[active_name]["socket"].recv(1024).decode()
                body = json.loads(buffer)

                if body["type"] == "logout":
                    # 用户退出时关闭连接, 然后从active_list中删除该用户
                    self.active_dict[active_name]["socket"].close()
                    self.active_dict.pop(active_name)
                    # 结束该用户线程
                    break
                
                elif body["type"] == "broadcast":
                    self.braodcast(active_name, body["content"])
                
                # elif body["type"] == "chat":
                else:
                    target_name = body["to"]
                    if target_name in self.active_dict.keys():
                        # 如果目标用户在活动列表中, 则发送消息
                        target_socket = self.active_dict[target_name]["socket"]
                        target_socket.send(buffer.encode())
                    else:
                        # 如果目标用户不在活动列表中, 则暂存消息
                        self.message_queue.setdefault(target_name, []).append(body)

            except Exception:
                logging.error(
                    f"连接失效: {self.active_dict[active_name]['socket'].getsockname()}, {self.active_dict[active_name]['socket'].fileno()}"
                )
                self.active_dict[active_name]["socket"].close()
                self.active_dict.pop(active_name)

    def wait_for_login(self, active_socket, addr):
        """对于服务器端接收到的连接, 进入等待登录函数, 等待该连接的发起方发送登录或注册信息

        Args:
            active_socket (socket.socket): 收到的连接
            addr (tuple(ip, port)): 连接来源
        """
        try:
            buffer = active_socket.recv(1024).decode()
            body = json.loads(buffer)
            if body["type"] == "login":
                data_base_info = get_user(body["username"])
                if data_base_info != None and body["password"] == data_base_info[1]:
                    # 数据库中有并且密码正确
                    activer = {
                        "socket": active_socket,
                        "ip": addr[0],
                        "port": addr[1],
                    }
                    self.active_dict.setdefault(body["username"], activer)
                    active_socket.send(
                        json.dumps(
                            {
                                "type": "approval",
                                "content": f"{body['username']} is logged in",
                            }
                        ).encode()
                    )

                    # 在登录成功后检查离线消息
                    if body["username"] in self.message_queue.keys():
                        for msg in self.message_queue[body["username"]]:
                            if msg["type"] == "chat":
                                active_socket.send(json.dumps(msg).encode())
                            elif msg["type"].startswith("ftp"):
                                # 待实现: 离线文件传输
                                pass
                    # 删除已读消息
                    self.message_queue.pop(body["username"])

                    # 开启用户线程
                    thread = threading.Thread(target=self.user_thread, args=(body["username"],), daemon=True)
                    thread.start()
                else:
                    active_socket.send(
                        json.dumps(
                            {"type": "denial", "content": "login failed"}
                        ).encode()
                    )

            elif body["type"] == "signup":
                if data_base_info == None:
                    # 数据库中没有该用户名, 则注册之
                    add_user(body["username"], body["password"])
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

    def start(self):
        """服务器, 启动!"""
        logging.info(f"绑定地址 {IP}:{PORT}")
        self.server.bind((IP, PORT))
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
