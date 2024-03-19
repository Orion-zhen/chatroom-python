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

        """活动中的用户列表
        active_list = [
            {
                "socket": socket,
                "ip": ip,
                "port": port,
                "username": username
            },
        ]
        """
        self.avtive_list = []

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
        for i, connection in enumerate(self.avtive_list):
            if connection["username"] == username:
                connection["socket"].send(
                    json.dumps(
                        {"type": "braodcast", "from": username, "content": message}
                    ).encode()
                )

    def user_thread(self, activer):
        """专门接收该用户消息并进行处理的线程
        可以进行的操作有: 私聊, 广播, 传输文件, 语音聊天

        Args:
            activer (dict): 用户和服务器连接记录, 是self.avtive_list中的一个元素
        """
        while True:
            try:
                buffer = activer["socket"].recv(1024).decode()
                body = json.loads(buffer)

                if body["type"] == "logout":
                    # 用户退出时关闭连接, 然后从connections中删除该用户
                    activer["socket"].close()
                    self.avtive_list.remove(activer)
                    # 结束该用户线程
                    break

                elif body["type"] == "chat":
                    found_target = False
                    # 遍历在线用户列表, 并将消息发送给该用户
                    for target in self.avtive_list:
                        if target["username"] == body["to"]:
                            found_target = True
                            target["socket"].send(buffer.encode())
                            break
                    # 如果未找到该在线用户, 则暂存至消息队列中
                    if not found_target:
                        self.message_queue.append(body)

            except Exception:
                logging.error(
                    f"连接失效: {activer['socket'].getsockname()}, {activer['socket'].fileno()}"
                )
                activer["socket"].close()
                self.avtive_list.remove(activer)

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
                        "username": body["username"],
                    }
                    self.avtive_list.append(activer)
                    active_socket.send(
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
                            if msg["to"] == body["username"] and msg["type"] == "chat":
                                active_socket.send(json.dumps(msg).encode())
                                index_to_drop.append(i)
                    # 删除已读消息
                    if len(index_to_drop) > 0:
                        self.message_queue = list(
                            filter(lambda x: x not in index_to_drop, self.message_queue)
                        )

                    # 开启用户线程
                    thread = threading.Thread(target=self.user_thread, args=(activer,))
                    thread.setDaemon(True)
                    thread.start()
                else:
                    active_socket.send(
                        json.dumps(
                            {"type": "denial", "detail": "login failed"}
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
                            {"type": "denial", "detail": "username already exists"}
                        ).encode()
                    )

        except Exception:
            logging.error(
                f"无法连接: {active_socket.getsockname()}, {active_socket.fileno()}"
            )

    def start(self):
        """服务器, 启动!"""
        logging.info(f"绑定地址 {IP}:{PORT}")
        self.server.bind((IP, PORT))
        logging.info(f"启动服务器")
        self.server.listen(10)

        # 初始化连接
        self.avtive_list.clear()
        self.message_queue.clear()

        # 开始监听
        while True:
            try:
                connection, addr = self.server.accept()
                logging.info(f"连接来自 {addr[0]}:{addr[1]}")
                # 开启新线程
                thread = threading.Thread(
                    target=self.wait_for_login, args=(connection, addr)
                )
                thread.setDaemon(True)
                thread.start()

            except Exception:
                logging.error(
                    f"连接异常: {connection.getsockname()}, {connection.fileno()}"
                )
