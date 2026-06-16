import threading
import psutil
import time
import subprocess
import os
import re

def get_pid():
    command = "ps aux | grep code | grep -v grep | sort -h | head -n 1"
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    output_lines = result.stdout.strip().split('\n')[0]
    output_lines = output_lines.strip().split()
    run = True
    while run:
        try:
            pid = int(output_lines[0])
            run = False
        except:
            output_lines.pop(0)
    return pid

def get_child_processes(pid):
    try:
        parent = psutil.Process(pid)
        return parent.children(recursive=True)      
    except psutil.NoSuchProcess:
        return []

def monitor_strace_log(pid):
    all_files = []
    run = 1
    while run > 0 :
        run -= 1
        time.sleep(1)  # Проверяем файл каждую секунду
        if os.path.exists('/tmp/asd/'):
            for file in os.listdir("/tmp/asd"):
                with open("/tmp/asd/"+file, 'r') as strace_log:
                    lines = strace_log.readlines()
                    for line in lines:
                        #pid = file.split("file_log")[1]

                        #print(line)
                        if "read" in line:
                            match = int(line.split("(")[1].split(",")[0])
                            fd = match
                            child_fd_path = f"/proc/{pid}/fd/{fd}"
                            try:
                                child_fd_link = os.readlink(child_fd_path)
                                if '/' in child_fd_link:
                                    all_files.append('r ' + child_fd_link)
                            except FileNotFoundError:
                                continue

                        elif "write" in line:
                            match = int(line.split("(")[1].split(",")[0])
                            fd = match
                            child_fd_path = f"/proc/{pid}/fd/{fd}"
                            try:
                                child_fd_link = os.readlink(child_fd_path)
                                if '/' in child_fd_link:
                                    all_files.append('w ' + child_fd_link)
                            except:
                                continue

        with open('files_read.log', 'w') as read_file:
            with open('files_write.log', 'w') as write_file:
                all_files = list(set(all_files))
                for i in all_files:
                    if i[0] == 'r':
                        read_file.write(i[2:] + '\n')
                    else:
                        write_file.write(i[2:] + '\n')
                                

if __name__ == "__main__":
    while True:
        try:
            pid = get_pid()
            print(f"PID получен, начинаю логирование процесса {pid}")
            monitor_strace_log(pid)
        except:
            continue
            print("Пожалуйста, введите корректный числовой PID.")
        time.sleep(10)
