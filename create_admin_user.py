import json
import os
from werkzeug.security import generate_password_hash

# 配置文件路径
CONFIG_FILE = 'config.json'

# 新管理员用户信息
NEW_USERNAME = 'temp_admin'
NEW_PASSWORD = 'temp_admin123'

# 读取现有配置
if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)
else:
    print(f"配置文件 {CONFIG_FILE} 不存在")
    exit(1)

# 添加/更新管理员用户
config['users'][NEW_USERNAME] = {
    'password': generate_password_hash(NEW_PASSWORD),
    'role': 'admin',
    'accessible_dirs': []
}

# 保存配置
with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)

print(f"管理员用户 '{NEW_USERNAME}' 创建成功!")
print(f"用户名: {NEW_USERNAME}")
print(f"密码: {NEW_PASSWORD}")