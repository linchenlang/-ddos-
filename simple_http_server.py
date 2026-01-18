# simple_http_server.py - 用于测试的简单HTTP服务器
import socket
import threading
import time
from datetime import datetime

class SimpleHTTPServer:
    def __init__(self, host='0.0.0.0', port=8080):
        self.host = host
        self.port = port
        self.request_count = 0
        self.start_time = time.time()
        self.lock = threading.Lock()
        
    def handle_request(self, client_socket, address):
        """处理单个HTTP请求"""
        with self.lock:
            self.request_count += 1
            count = self.request_count
        
        try:
            # 接收请求
            request = client_socket.recv(1024).decode('utf-8')
            
            # 记录请求
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{current_time}] 请求 #{count} 来自 {address}")
            
            # 简单的HTTP响应
            response_body = f"""
            <html>
            <head><title>测试服务器</title></head>
            <body>
                <h1>测试HTTP服务器</h1>
                <p>时间: {current_time}</p>
                <p>请求编号: #{count}</p>
                <p>客户端: {address}</p>
                <p>服务器运行时间: {time.time() - self.start_time:.1f}秒</p>
                <p>总请求数: {count}</p>
            </body>
            </html>
            """
            
            response = f"""HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Content-Length: {len(response_body)}
Connection: close

{response_body}"""
            
            client_socket.send(response.encode('utf-8'))
            
        except Exception as e:
            print(f"处理请求错误: {e}")
        finally:
            client_socket.close()
    
    def start(self):
        """启动服务器"""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.host, self.port))
        server.listen(5)
        
        print(f"HTTP服务器启动在 {self.host}:{self.port}")
        print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("按 Ctrl+C 停止服务器\n")
        
        try:
            while True:
                client_socket, address = server.accept()
                thread = threading.Thread(target=self.handle_request, args=(client_socket, address))
                thread.daemon = True
                thread.start()
        except KeyboardInterrupt:
            print("\n服务器停止")
        finally:
            server.close()
            print(f"\n服务器统计:")
            print(f"总运行时间: {time.time() - self.start_time:.1f}秒")
            print(f"总请求数: {self.request_count}")
            print(f"平均请求率: {self.request_count/(time.time() - self.start_time):.1f} 请求/秒")

if __name__ == "__main__":
    server = SimpleHTTPServer('127.0.0.1', 8080)
    server.start()