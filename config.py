import os
import json
from typing import Dict, List

class Config:
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self) -> Dict:
        """加载配置文件"""
        default_config = {
            "users": {
                "admin": {
                    "password": "admin123",
                    "role": "admin",
                    "accessible_dirs": []  # 管理员可以访问所有目录
                }
            },
            "image_directories": [],
            "thumbnail_size": [256, 256],
            "preview_max_size": 1920,
            "supported_formats": [".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp", ".raw", ".cr2", ".nef", ".arw", ".dng"],
            "server": {
                "host": "0.0.0.0",
                "port": 5000,
                "debug": True
            }
        }
        
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # 合并默认配置和加载的配置
                    default_config.update(loaded_config)
            except Exception as e:
                print(f"加载配置文件失败: {e}")
        
        return default_config
    
    def save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置文件失败: {e}")
    
    def add_user(self, username: str, password: str, accessible_dirs: List[str] = None):
        """添加用户"""
        self.config['users'][username] = {
            'password': password,
            'role': 'user',
            'accessible_dirs': accessible_dirs or []
        }
        self.save_config()
    
    def add_image_directory(self, directory: str):
        """添加图片目录"""
        if directory not in self.config['image_directories']:
            self.config['image_directories'].append(directory)
            self.save_config()
    
    def get_user_accessible_dirs(self, username: str) -> List[str]:
        """获取用户可访问的目录"""
        user = self.config['users'].get(username)
        if not user:
            return []
        
        if user['role'] == 'admin':
            return self.config['image_directories']
        else:
            return user['accessible_dirs']
    
    def verify_user(self, username: str, password: str) -> bool:
        """验证用户"""
        user = self.config['users'].get(username)
        return user and user['password'] == password
