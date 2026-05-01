from datetime import datetime
import pytz
from config import Config
 
class Timestamps:
    def __init__(self, nombre):
        self.nombre = str(nombre)
        self.timestamp = datetime.now()
 
    def get_nombre(self):
        return self.nombre
 
    def get_timestamp(self):
        return self.timestamp
   
 
    def setZone(): #Para la zona horaria España.
        now=datetime.now()
        timezone_spain = pytz.timezone('Europe/Madrid')
        now_spain = now.astimezone(timezone_spain)
        return now_spain