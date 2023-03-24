# Клиент парсинга

## Запуск

СНАЧАЛА 

Поменять в файле ```user_settings.json``` параметры
```json

{
  "name": "test",
  "server": {
    "init_timeout": 10,
    "url": поставить адрес, который я скажу
  },
  "selenium": {
    "chromedriver_path": поставить АБСОЛЮТНЫЙ путь к файлу chromedriver.exe, его надо скачать,
    "chromedriver_data_dir": поставить АБСОЛЮТНЫЙ путь к существующей(лучше будет) ,
    "log_in_timeout": 90
  }
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
