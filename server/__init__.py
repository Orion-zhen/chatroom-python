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
        logging.info(f"绑定地址 {IP}:{PORT}")
        self.server.bind((IP, PORT))
        """活动中的用户列表
        connections = [
            {
                "socket": socket,
                "ip": ip,
                "port": port,
                "username": username
            },
        ]
        """
        self.connections = []

        """消息队列
        message_queue = [
            {
                "type": "chat",
                "from": "<selfname>",
                "to": "<username>",
                "content": "<content>"
            }
        ]
        """
        self.message_queue = []

    def braodcast(self, username="system", message=""):
        """广播消息

        Args:
            username (str, optional): 发送广播消息的用户名称. Defaults to "system".
            message (str, optional): 广播的消息内容. Defaults to "".
        """
        for i, connection in enumerate(self.connections):
            if connection["username"] == username:
                connection["socket"].send(
                    json.dumps(
                        {"type": "braodcast", "from": username, "content": message}
                    ).encode()
                )

    def user_thread(self, connection):
        """专门接收该用户消息并进行处理的线程
        可以进行的操作有: 私聊, 广播, 传输文件, 语音聊天

        Args:
            connection (socket.socket): 用户和服务器连接的socket
        """
        pass

    def wait_for_login(self, connection, addr):
        """对于服务器端接收到的连接, 进入等待登录函数, 等待该连接的发起方发送登录或注册信息

        Args:
            connection (socket.socket): 收到的连接
            addr (tuple(ip, port)): 连接来源
        """
        try:
            buffer = connection.recv(1024).decode()
            body = json.loads(buffer)
            if body["type"] == "login":
                data_base_info = get_user(body["username"])
                if data_base_info != None and body["password"] == data_base_info[1]:
                    # 数据库中有并且密码正确
                    user_info = {
                        "socket": connection,
                        "ip": addr[0],
                        "port": addr[1],
                        "username": body["username"],
                    }
                    self.connections.append(user_info)
                    connection.send(
                        json.dumps(
                            {
                                "type": "approval",
                                "detail": f"{body['username']} is logged in",
                            }
                        ).encode()
                    )

                    # 在登录成功后检查离线消息
                    index_to_drop = []
                    if len(self.message_queue) > 0:
                        for i, msg in enumerate(self.message_queue):
                            if msg["to"] == body["username"]:
                                connection.send(
                                    f"{msg['from']}: {msg['content']}".encode()
                                )
                                index_to_drop.append(i)
                    # 删除已读消息
                    if len(index_to_drop) > 0:
                        self.message_queue = list(
                            filter(lambda x: x not in index_to_drop, self.message_queue)
                        )

                    thread = threading.Thread(
                        target=self.user_thread, args=(connection,)
                    )
                    thread.setDaemon(True)
                    thread.start()
                else:
                    connection.send(
                        json.dumps(
                            {"type": "denial", "detail": "login failed"}
                        ).encode()
                    )

            elif body["type"] == "signin":
                if data_base_info == None:
                    # 数据库中没有该用户名, 则注册之
                    add_user(body["username"], body["password"])
                else:
                    # 有, 则返回用户名冲突
                    connection.send(
                        json.dumps(
                            {"type": "denial", "detail": "username already exists"}
                        ).encode()
                    )

        except Exception:
            logging.error(
                f"无法连接: {connection.getsockname()}, {connection.fileno()}"
            )
