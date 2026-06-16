import subprocess
import time

def run_command_in_background():
    # Запускаем команду с перенаправлением вывода в файл
    command = "cat /dev/kmsg > /tmp/asd"
    process = subprocess.Popen(command, shell=True, stderr=subprocess.PIPE)

    return process

if __name__ == "__main__":
    process = run_command_in_background()
    print(f"Команда запущена в фоновом режиме с PID: {process.pid}")

    try:
        while True:
            time.sleep(1)  # Держим основной поток активным
    except KeyboardInterrupt:
        print("Завершение работы...")
        process.terminate()  # Завершаем процесс при прерывании
        process.wait()  # Ждем завершения процесса
        print("Процесс завершен.")
