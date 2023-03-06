# Клиент парсинга

## Запуск

СНАЧАЛА 

Поменять в файле ```settings.json``` параметры
```json
"id": 1 # ваш id

server: {
  "url": "46.138.248.205:4222" # проверить чтобы адрес был таким
} 

```


```shell
python -m venv venv

# WIN
./venv/Scripts/activate.bat
# LINUX
source ./venv/bin/activate

pip install -r requirements.txt
PYTHONPATH="/path/to/dir:$PYTHONPATH" python main.py

```