from dotenv import load_dotenv
import os
load_dotenv()

SERVER_URL = '0.0.0.0'
PORT = 9000
ENV = 'dev'
OPENCODE_ZEN_API_KEY = os.getenv('OPENCODE_ZEN_API_KEY')
