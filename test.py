import socket
import os

# 服务器设置
SERVER_IP = '0.0.0.0'
SERVER_PORT = 12345
FILE_PATH = 'large_file_to_send.txt'  # 要发送的文件路径

# 创建TCP套接字
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# 绑定IP和端口
server_socket.bind((SERVER_IP, SERVER_PORT))

# 设置最大连接数，超过后排队
server_socket.listen(5)

print(f"Server is listening on port {SERVER_PORT}...")

while True:
    # 接受客户端连接
    client_socket, client_address = server_socket.accept()
    print(f"Connected with {client_address[0]}:{client_address[1]}")

    # 发送文件
    with open(FILE_PATH, 'rb') as file:
        file_data = file.read()
        client_socket.sendall(file_data)

    # 关闭连接
    client_socket.close()
