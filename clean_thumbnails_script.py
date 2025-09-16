import requests
import json

# 服务器URL
BASE_URL = 'http://localhost:5000'

# 登录信息
USERNAME = 'temp_admin'
PASSWORD = 'temp_admin123'

# 1. 登录获取会话
print("登录中...")
login_response = requests.post(f"{BASE_URL}/api/login", json={
    'username': USERNAME,
    'password': PASSWORD
})

if login_response.status_code != 200:
    print(f"登录失败: {login_response.json().get('error', '未知错误')}")
    exit(1)

print("登录成功!")

# 获取登录后的cookie
session_cookie = login_response.cookies.get_dict()

# 2. 调用清理缩略图API
print("正在清理所有缩略图...")
clean_response = requests.post(
    f"{BASE_URL}/api/admin/clean_thumbnails",
    cookies=session_cookie
)

if clean_response.status_code == 200:
    result = clean_response.json()
    print(result.get('message', '缩略图清理成功'))
else:
    print(f"清理失败: {clean_response.json().get('error', '未知错误')}")