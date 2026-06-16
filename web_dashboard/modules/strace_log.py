import os
import subprocess
import psutil
import time

def get_child_processes(pid):
    try:
        parent = psutil.Process(pid)
        return parent.children(recursive=True)  # Получаем всех дочерних процессов
    except psutil.NoSuchProcess:
        return []


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

pid = get_pid()
print(pid)
os.system("rm -rf /tmp/asd")
os.system("mkdir /tmp/asd")
command = f"sudo strace -p {pid} -e trace=open,read,write -o /tmp/asd/file_log "
chils = get_child_processes(pid)
pids = []
for cpid in chils:
    command += f" & sudo strace -p {cpid.pid} -e trace=open,read,write -o /tmp/asd/file_log{cpid.pid} "
    pids.append(cpid.pid)

print(command)
print(len(pids))
subprocess.run("sudo sysctl kernel.yama.ptrace_scope=0", shell=True)

#command = f"sudo strace -p {pid} -e trace=open,read,write -o /tmp/file_log"

# Запуск команды в фоновом режиме
process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
output, error = process.communicate()
print("Команда запущена в фоновом режиме.")
print("Вывод команды:")
print(output.decode('utf-8'))
if error:
    print("Ошибка команды:")
    print(error.decode('utf-8'))