#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# permanent_limit_fixer.py - 永久提高Linux系统限制
# 用法: sudo python3 permanent_limit_fixer.py

import os
import sys
import subprocess

def check_root():
    """检查是否以root运行"""
    if os.geteuid() != 0:
        print("错误: 此脚本必须以root权限运行")
        print("请使用: sudo python3 permanent_limit_fixer.py")
        sys.exit(1)

def backup_file(filepath):
    """备份文件"""
    if os.path.exists(filepath):
        import shutil, time
        backup_path = f"{filepath}.backup_{int(time.time())}"
        shutil.copy2(filepath, backup_path)
        print(f"已备份: {filepath} -> {backup_path}")
        return True
    return False

def run_cmd(cmd):
    """运行命令并返回结果"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return False, "", str(e)

def fix_limits_conf():
    """修复/etc/security/limits.conf"""
    print("\n[1] 修复 /etc/security/limits.conf")
    
    backup_file("/etc/security/limits.conf")
    
    new_content = """# 系统限制配置 - 永久提高限制
* soft nofile 1048576
* hard nofile 1048576
* soft nproc 65535
* hard nproc 65535
root soft nofile 1048576
root hard nofile 1048576
root soft nproc 65535
root hard nproc 65535
"""
    
    try:
        with open("/etc/security/limits.conf", "a") as f:
            f.write("\n" + new_content)
        print("✓ 已更新limits.conf")
        return True
    except Exception as e:
        print(f"✗ 更新失败: {e}")
        return False

def fix_pam_config():
    """修复PAM配置"""
    print("\n[2] 修复PAM配置")
    
    pam_files = ["/etc/pam.d/common-session", "/etc/pam.d/login", "/etc/pam.d/sshd"]
    
    for pam_file in pam_files:
        if os.path.exists(pam_file):
            backup_file(pam_file)
            try:
                with open(pam_file, "r") as f:
                    content = f.read()
                
                if "pam_limits.so" not in content:
                    with open(pam_file, "a") as f:
                        f.write("\nsession required pam_limits.so\n")
                    print(f"✓ 已更新 {pam_file}")
                else:
                    print(f"✓ {pam_file} 已包含配置")
            except Exception as e:
                print(f"✗ 更新 {pam_file} 失败: {e}")
    
    return True

def fix_sysctl_conf():
    """修复/etc/sysctl.conf"""
    print("\n[3] 修复 /etc/sysctl.conf")
    
    backup_file("/etc/sysctl.conf")
    
    sysctl_settings = """
# 提高系统文件描述符限制
fs.file-max = 2097152
fs.nr_open = 2097152

# 提高进程限制
kernel.pid_max = 4194304
kernel.threads-max = 2097152

# 提高网络连接限制
net.core.somaxconn = 65535
net.core.netdev_max_backlog = 65536
net.ipv4.tcp_max_syn_backlog = 65536
net.ipv4.ip_local_port_range = 1024 65535

# 提高内存缓冲区
net.core.rmem_max = 134217728
net.core.wmem_max = 134217728
net.ipv4.tcp_rmem = 4096 87380 134217728
net.ipv4.tcp_wmem = 4096 65536 134217728
"""
    
    try:
        with open("/etc/sysctl.conf", "a") as f:
            f.write(sysctl_settings)
        print("✓ 已更新sysctl.conf")
        
        # 立即应用设置
        success, stdout, stderr = run_cmd("sysctl -p")
        if success:
            print("✓ 已应用sysctl设置")
        else:
            print(f"✗ 应用sysctl设置失败: {stderr}")
        
        return success
    except Exception as e:
        print(f"✗ 更新失败: {e}")
        return False

def fix_systemd_config():
    """修复systemd配置"""
    print("\n[4] 修复systemd配置")
    
    config_files = {
        "/etc/systemd/system.conf": [
            "DefaultLimitNOFILE=1048576",
            "DefaultLimitNPROC=65535",
            "DefaultTasksMax=infinity"
        ],
        "/etc/systemd/user.conf": [
            "DefaultLimitNOFILE=1048576",
            "DefaultLimitNPROC=65535"
        ]
    }
    
    for config_file, settings in config_files.items():
        if os.path.exists(config_file):
            backup_file(config_file)
            
            try:
                with open(config_file, "r") as f:
                    lines = f.readlines()
                
                new_lines = []
                for line in lines:
                    line_stripped = line.strip()
                    replaced = False
                    
                    for setting in settings:
                        key = setting.split("=")[0]
                        if line_stripped.startswith(key + "="):
                            # 注释掉原有设置，添加新的
                            if not line_stripped.startswith("#"):
                                new_lines.append("# " + line)
                            new_lines.append(setting + "\n")
                            replaced = True
                            break
                    
                    if not replaced:
                        new_lines.append(line)
                
                # 添加缺失的设置
                for setting in settings:
                    key = setting.split("=")[0]
                    if not any(line.strip().startswith(key + "=") for line in new_lines):
                        new_lines.append(setting + "\n")
                
                with open(config_file, "w") as f:
                    f.writelines(new_lines)
                
                print(f"✓ 已更新 {config_file}")
            except Exception as e:
                print(f"✗ 更新 {config_file} 失败: {e}")
    
    return True

def create_bashrc_fix():
    """为用户bashrc添加设置"""
    print("\n[5] 为用户bashrc添加设置")
    
    bashrc_content = """
# 提高shell限制
ulimit -n 1048576 >/dev/null 2>&1
ulimit -u 65535 >/dev/null 2>&1
"""
    
    # 为当前用户和root添加
    users = []
    
    # 获取当前用户（如果是sudo运行）
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        users.append(sudo_user)
    
    users.append("root")
    
    for user in users:
        try:
            # 获取用户家目录
            success, home_dir, _ = run_cmd(f"getent passwd {user} | cut -d: -f6")
            if not success or not home_dir:
                continue
            
            bashrc_path = os.path.join(home_dir, ".bashrc")
            
            if os.path.exists(bashrc_path):
                with open(bashrc_path, "r") as f:
                    content = f.read()
                
                if "ulimit -n 1048576" not in content:
                    with open(bashrc_path, "a") as f:
                        f.write(bashrc_content)
                    print(f"✓ 已更新 {user} 的 .bashrc")
                else:
                    print(f"✓ {user} 的 .bashrc 已包含设置")
            else:
                # 创建.bashrc
                with open(bashrc_path, "w") as f:
                    f.write(bashrc_content)
                run_cmd(f"chown {user}:{user} {bashrc_path}")
                print(f"✓ 已创建 {user} 的 .bashrc")
                
        except Exception as e:
            print(f"✗ 处理用户 {user} 失败: {e}")
    
    return True

def create_test_script():
    """创建测试脚本"""
    print("\n[6] 创建测试脚本")
    
    test_script = "/tmp/test_limits.py"
    test_code = '''#!/usr/bin/env python3
import os, resource, socket

print("当前系统限制测试:")
print("="*50)

# 文件描述符限制
soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
print(f"文件描述符限制: 软={soft:,}, 硬={hard:,}")

# 进程限制
soft_proc, hard_proc = resource.getrlimit(resource.RLIMIT_NPROC)
print(f"进程数限制: 软={soft_proc:,}, 硬={hard_proc:,}")

# 测试socket创建
print("\\n测试socket创建能力...")
sockets = []
max_sockets = 0
try:
    for i in range(1000):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.1)
        sockets.append(sock)
        max_sockets = i + 1
except Exception as e:
    print(f"在创建 {max_sockets} 个socket后出错: {type(e).__name__}")
finally:
    for sock in sockets:
        try:
            sock.close()
        except:
            pass

print(f"成功创建 {max_sockets} 个socket")

# 评估
print("\\n评估:")
if soft >= 100000:
    print("✓ 文件描述符限制足够高")
else:
    print("⚠ 文件描述符限制较低")

if max_sockets >= 500:
    print("✓ socket创建测试通过")
else:
    print("⚠ socket创建数量有限")

print("="*50)
'''
    
    try:
        with open(test_script, "w") as f:
            f.write(test_code)
        os.chmod(test_script, 0o755)
        print(f"✓ 测试脚本已创建: {test_script}")
        print(f"  运行命令: python3 {test_script}")
        return True
    except Exception as e:
        print(f"✗ 创建测试脚本失败: {e}")
        return False

def show_current_limits():
    """显示当前限制"""
    print("\n当前系统限制:")
    print("="*50)
    
    cmds = [
        ("用户文件描述符限制", "ulimit -n"),
        ("用户进程数限制", "ulimit -u"),
        ("系统文件描述符限制", "cat /proc/sys/fs/file-max"),
        ("最大连接队列", "cat /proc/sys/net/core/somaxconn"),
        ("临时端口范围", "cat /proc/sys/net/ipv4/ip_local_port_range"),
    ]
    
    for name, cmd in cmds:
        success, stdout, stderr = run_cmd(cmd)
        if success:
            print(f"{name}: {stdout}")
        else:
            print(f"{name}: 无法读取")
    
    print("="*50)

def main():
    print("="*60)
    print("Linux系统永久限制提高工具")
    print("="*60)
    print("此脚本将永久提高以下限制:")
    print("  - 文件描述符数量 (nofile): 1,048,576")
    print("  - 进程数 (nproc): 65,535")
    print("  - 网络连接相关限制")
    print("="*60)
    
    # 检查root权限
    check_root()
    
    # 显示当前限制
    show_current_limits()
    
    # 确认
    confirm = input("\n是否继续? (y/N): ").strip().lower()
    if confirm != 'y':
        print("操作取消")
        return
    
    # 执行修复步骤
    steps = [
        ("修复limits.conf", fix_limits_conf),
        ("修复PAM配置", fix_pam_config),
        ("修复sysctl.conf", fix_sysctl_conf),
        ("修复systemd配置", fix_systemd_config),
        ("为用户bashrc添加设置", create_bashrc_fix),
        ("创建测试脚本", create_test_script),
    ]
    
    for step_name, step_func in steps:
        step_func()
    
    print("\n" + "="*60)
    print("修复完成!")
    print("="*60)
    print("重要提示:")
    print("1. 部分设置需要重新登录或重启才能完全生效")
    print("2. 建议重新打开终端或重启系统")
    print("3. 运行测试脚本检查限制是否生效:")
    print(f"   python3 /tmp/test_limits.py")
    print("4. 如果仍有问题，请检查是否有其他配置文件覆盖了这些设置")
    print("="*60)
    
    # 立即尝试应用用户限制
    print("\n立即应用用户限制...")
    run_cmd("ulimit -n 1048576 2>/dev/null || true")
    run_cmd("ulimit -u 65535 2>/dev/null || true")
    
    print("\n请重新登录或重启系统使所有设置完全生效!")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n操作被用户中断")
    except Exception as e:
        print(f"\n错误: {e}")