import time
import schedule
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "Reelix Discovery Agent Worker"
    class Config:
        env_file = ".env"

settings = Settings()

def tick():
    print(f"[worker] {settings.app_name} heartbeat")

schedule.every(1).minutes.do(tick)

if __name__ == "__main__":
    print("[worker] starting...")
    tick()
    while True:
        schedule.run_pending()
        time.sleep(1)

