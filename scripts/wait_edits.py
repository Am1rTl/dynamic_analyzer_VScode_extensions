import os
import time

def watch_file(file_path):
    # Получаем начальное время изменения файла
    last_modified_time = os.path.getmtime(file_path)

    print(f"Начало наблюдения за файлом: {file_path}")

    while True:
        time.sleep(1)  # Задержка перед следующей проверкой
        # Получаем текущее время изменения файла
        current_modified_time = os.path.getmtime(file_path)

        # Проверяем, изменилось ли время
        if current_modified_time != last_modified_time:
            print(f"Файл '{file_path}' был изменен.")
            last_modified_time = current_modified_time  # Обновляем время

if __name__ == "__main__":
    file_to_watch = '/tmp/asd'  # Укажите путь к файлу, который нужно отслеживать
    watch_file(file_to_watch)
