import os
import json
import hashlib
import shutil
from typing import Dict, List
from werkzeug.security import check_password_hash, generate_password_hash

class Config:
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.baseline_file = 'config_baseline.json'  # 配置基准文件
        self.config = self.load_config()
        self.config_hash = None  # 初始化时不计算哈希
        self.last_config_check = self.load_config_baseline()  # 从文件加载配置基准
    
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
            'password': generate_password_hash(password),
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
        if not user:
            return False
        
        # 如果是明文密码，转换为哈希存储
        if not user['password'].startswith('pbkdf2:sha256:'):
            # 升级为哈希密码
            user['password'] = generate_password_hash(password)
            self.save_config()
            return True
        
        return check_password_hash(user['password'], password)
    
    def load_config_baseline(self) -> Dict:
        """加载配置基准"""
        if os.path.exists(self.baseline_file):
            try:
                with open(self.baseline_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载配置基准失败: {e}")
        return None
    
    def save_config_baseline(self, baseline_config: Dict):
        """保存配置基准"""
        try:
            with open(self.baseline_file, 'w', encoding='utf-8') as f:
                json.dump(baseline_config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置基准失败: {e}")
    
    def _calculate_config_hash(self) -> str:
        """计算配置文件的哈希值，用于检测变更"""
        # 只计算影响缓存的关键配置项
        cache_related_config = {
            'thumbnail_size': self.config.get('thumbnail_size'),
            'thumbnail_quality': self.config.get('thumbnail_quality'),
            'preview_max_size': self.config.get('preview_max_size'),
            'preview_quality': self.config.get('preview_quality')
        }
        config_str = json.dumps(cache_related_config, sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()
    
    def check_config_changes(self) -> Dict[str, bool]:
        """检查配置是否发生变更，返回需要处理的变更类型"""
        changes = {
            'thumbnail_changed': False,
            'preview_changed': False
        }
        
        # 如果是第一次检查，记录当前配置作为基准
        if self.last_config_check is None:
            self.last_config_check = {
                'thumbnail_size': self.config.get('thumbnail_size'),
                'thumbnail_quality': self.config.get('thumbnail_quality'),
                'preview_max_size': self.config.get('preview_max_size'),
                'preview_quality': self.config.get('preview_quality')
            }
            print(f"初始化配置基准: {self.last_config_check}")
            self.save_config_baseline(self.last_config_check)
            return changes
        
        # 重新加载配置文件
        old_config = self.last_config_check.copy()
        self.config = self.load_config()
        
        current_config = {
            'thumbnail_size': self.config.get('thumbnail_size'),
            'thumbnail_quality': self.config.get('thumbnail_quality'),
            'preview_max_size': self.config.get('preview_max_size'),
            'preview_quality': self.config.get('preview_quality')
        }
        
        print(f"检查配置变更:")
        print(f"  旧配置: {old_config}")
        print(f"  新配置: {current_config}")
        
        # 检查具体变更
        if (old_config.get('thumbnail_size') != current_config.get('thumbnail_size') or
            old_config.get('thumbnail_quality') != current_config.get('thumbnail_quality')):
            changes['thumbnail_changed'] = True
            print(f"缩略图配置变更: {old_config.get('thumbnail_size')} -> {current_config.get('thumbnail_size')}")
        
        if (old_config.get('preview_max_size') != current_config.get('preview_max_size') or
            old_config.get('preview_quality') != current_config.get('preview_quality')):
            changes['preview_changed'] = True
            print(f"预览图配置变更: {old_config.get('preview_max_size')} -> {current_config.get('preview_max_size')}")
        
        if changes['thumbnail_changed'] or changes['preview_changed']:
            print("检测到配置文件变更")
            # 更新基准配置
            self.last_config_check = current_config
            self.save_config_baseline(current_config)
        else:
            print("配置文件未发生变更")
        
        return changes
    
    def clear_cache_directories(self, image_directories: List[str]):
        """清理缓存目录"""
        for directory in image_directories:
            if os.path.exists(directory):
                cache_dir = os.path.join(directory, '.album_cache')
                if os.path.exists(cache_dir):
                    try:
                        shutil.rmtree(cache_dir)
                        print(f"已清理缓存目录: {cache_dir}")
                    except Exception as e:
                        print(f"清理缓存目录失败 {cache_dir}: {e}")
        
        # 清理项目根目录下的旧缓存文件夹（如果存在）
        old_cache_dir = 'cache'
        if os.path.exists(old_cache_dir):
            try:
                shutil.rmtree(old_cache_dir)
                print(f"已清理旧缓存目录: {old_cache_dir}")
            except Exception as e:
                print(f"清理旧缓存目录失败: {e}")
