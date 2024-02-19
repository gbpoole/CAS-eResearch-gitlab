import json
import requests
import pandas as pd
from io import StringIO
from decouple import config
from .events import DataSet

# Configure logger

class Client(object):
    def __init__(self,url="https://cas-eresearch-gitlab.adacs-gpoole.cloud.edu.au",token=None):
        self.url = url
        if not token:
            # Parse runtime configuration
            self.token = config('SECRET_TOKEN', default = None)
        else:
            self.token = token

        self.headers = {
            'X-Gitlab-Token': self.token,
        }

    def get(self):
        response = requests.get(f'{self.url}/events', headers=self.headers)
        df = pd.read_json(StringIO(response.json()))
        df.index.name = 'date'
        return DataSet(df=df)
