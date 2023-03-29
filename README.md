# Клиент парсинга

## Запуск

СНАЧАЛА 

Поменять в файле ```user_settings.json``` параметры
```json

{
  "name": "test",
  "enable_offline_mode": true | false поставить актуальное
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
python -m venv venv

# WIN
./venv/Scripts/activate.bat
# LINUX
source ./venv/bin/activate

pip install -r requirements.txt

# WIN
set PYTHONPATH=`%cd%`
# LINUX
export PYTHONPATH=`pwd`

python main.py

```

## Оффлайн режим

В оффлайн режиме с парсером можно взаимодействовать через cli.py в том же окружении

Для отображения возможных опций
```
# WIN
./venv/Scripts/activate.bat
# LINUX
source ./venv/bin/activate

python cli.py
```