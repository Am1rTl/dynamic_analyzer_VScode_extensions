import socket
from functools import lru_cache

# Кэш для хранения известных IP -> hostname
@lru_cache(maxsize=1000)
def get_hostname(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except socket.herror:
        return None

def get_logs():
    import re

    # Sample log entries
    with open("/tmp/asda", 'r') as f:
        data = f.read()
    logs = data.split("\n")
    #print(logs)
    # Process and format logs
    new = []
    for log in logs:
        try:
            log = log.strip()  # Remove any leading/trailing whitespace
            time = log.split(',')[2]
            dst_port = log.split("DPT=")[1].split(' ')[0]
            dst = log.split("DST=")[1].split(' ')[0]
            lenght = log.split("LEN=")[1].split(' ')[0]
            
            # Получаем hostname
            hostname = get_hostname(dst)
            hostname_str = f" [HOST]={hostname}" if hostname else ""
            
            new.append(f"{time:5}, [DEST]={dst:15} [PORT]={dst_port:5} [Pack len]={lenght:5}{hostname_str}")
        except:
            continue
    return new
