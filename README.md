# Сервис по сокращению ссылок


## О возможностях сервиса
1. Авторизация пользователя - отправление пароля и имя пользователя на сервер. 
2. Отправка и сохранение захешируемого пароля на сервер. Если пользователь уже существует, то сервер вернёт ошибку
3. Пользователь отправляет запрос с именем пользователя и паролем для аутентификации.
4. Сервер проверяет правильность данных и генерирует JWT токен, который затем отправляется пользователю.
5. Если токен предоставлен пользовтелю, то ряд эндпоинтов будет теперь доступен ему автоматически, без токена - "Не авторизован"
![image](https://github.com/user-attachments/assets/8cc1ea80-cd21-42d5-81aa-fe0f09c89065)

## Как запустить?
- Запуск локально
git clone https://github.com/VladislavTokarev02/short_links


pip install -r requirements.txt


uvicorn app.main:app --host 0.0.0.0 --port 8000

- Запуск через Docker
docker-compose up --build

| id (int) | username (varchar) | password_hash (varchar) |


### Таблица links

| id (int) | original_url (varchar) | short_code (varchar) | expires_at (int) | click_count (int) | created_at (datetime)     | last_used (datetime) | user_id (int) |



