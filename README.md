# Клиент парсинга

## Запуск

СНАЧАЛА 

Поменять в файле ```settings.json``` параметры
```json
"id": 1 // ваш id

server: {
  "url": "46.138.248.205:4222" // проверить чтобы адрес был таким
}

selenium: {
    "chromedriver_path": "chromedriver" // лучше чтобы пути были абсолютными
    "chromedriver_data_dir": "chromedriver_data" // лучше чтобы пути были абсолютными
}

```


```shell
wget https://chromedriver.storage.googleapis.com/110.0.5481.77/chromedriver_win32.zip
unzip chromedriver_win32.zip chromedriver

python -m venv venv

# WIN
./venv/Scripts/activate.bat
# LINUX
source ./venv/bin/activate

pip install -r requirements.txt
PYTHONPATH=`:$PYTHONPATH` python main.py

```