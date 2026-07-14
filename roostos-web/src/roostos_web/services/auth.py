from typing import List
from fastapi import Depends
from roostos_engine.config import SystemConfig, UserConfig
from roostos_engine.repository import ConfigRepository
from roostos_web.services.base import get_repository

class AuthService:
    def __init__(self, repo: ConfigRepository = Depends(get_repository)):
        self.repo = repo

    def get_users(self) -> List[UserConfig]:
        config = self.repo.get_config()
        return config.users

    def update_users(self, users: List[UserConfig]):
        config = self.repo.get_config()
        system_config_obj = SystemConfig(
            system=config.system,
            users=users
        )
        self.repo.save_system_config(system_config_obj)
