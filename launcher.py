import threading
import time
import webbrowser
import os
from urllib.request import urlopen

import uvicorn
from app.main import app


def open_browser():
    url = 'http://127.0.0.1:8000'
    for _ in range(120):
        try:
            with urlopen(f'{url}/health', timeout=0.5):
                time.sleep(0.5)
                webbrowser.open(url)
                return
        except Exception:
            time.sleep(0.5)


if __name__ == '__main__':
    if os.getenv('FOIA_NO_BROWSER', '').lower() not in ('1', 'true', 'yes'):
        threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app, host='127.0.0.1', port=8000, access_log=False)
