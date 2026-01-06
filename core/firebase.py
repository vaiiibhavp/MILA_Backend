import firebase_admin
from firebase_admin import credentials
from config.basic_config import settings

def init_firebase():
    if not firebase_admin._apps:
        cred = credentials.Certificate(settings.FIREBASE_CRED_PATH)
        print("Cred: ", cred)
        print("settings.FIREBASE_CRED_PATH: ", settings.FIREBASE_CRED_PATH)
        firebase_admin.initialize_app(cred)
