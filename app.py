from flask import Flask, render_template, request, jsonify, session, send_file
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import os
import json
import sys
import argparse
from datetime import datetime, timedelta
from config import Config
from image_processor import ImageProcessor
import shutil
import atexit
from functools import wraps

app = Flask(__name__)
import os
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False  # 开发环境设为False，生产环境应设为True
app.config['SESSION_COOKIE_MAX_AGE'] = 604800  # 7天，与permanent_session_lifetime保持一致
CORS(app)

# 解析命令行参数
def parse_args():
    parser = argparse.ArgumentParser(description='相册管理工具')
    parser.add_argument('--clear-cache', action='store_true', 
                       help='清理所有缩略图和预览图缓存')
    parser.add_argument('--rebuild-cache', action='store_true',
                       help='清理并重新生成所有缓存')
    return parser.parse_args()

# 初始化配置和图片处理器
config = Config()
image_processor = ImageProcessor(config)

# 使用固定的密钥，确保重启后session不会失效
# 优先从环境变量读取，否则使用配置文件中的值，最后才生成随机密钥
app.secret_key = os.environ.get('SECRET_KEY', config.config.get('server', {}).get('secret_key', os.urandom(24).hex()))

# 配置session
session_config = config.config.get('session', {})
app.permanent_session_lifetime = timedelta(seconds=session_config.get('permanent_session_lifetime', 86400))

# 获取配置中的图片目录
image_directories = config.config.get('image_directories', [])

# 处理命令行参数
args = parse_args()

if len(sys.argv) > 1 and sys.argv[1] == '--rebuild-cache':
    print("正在清理缓存...")
    # 清理所有缓存
    image_processor.clean_all_cache()
    print("缓存清理完成！")
    
    if len(sys.argv) > 2 and sys.argv[2] == '--config-changed':
        print("配置文件已更改，正在重新生成缓存...")
    else:
        print("正在重新生成缓存...")
        # 预生成所有图片的缓存（递归处理所有子目录）
        for directory in image_directories:
            if os.path.exists(directory):
                print(f"正在处理目录: {directory}")
                images = image_processor.scan_directory(directory)  # 使用递归扫描
                total = len(images)
                for i, image in enumerate(images, 1):
                    try:
                        # 生成缩略图
                        image_processor.generate_thumbnail(image['file_path'])
                        # 生成预览图
                        image_processor.generate_preview(image['file_path'])
                        print(f"进度: {i}/{total} - {image['metadata']['filename']}")
                    except Exception as e:
                        print(f"处理失败 {image['metadata']['filename']}: {e}")
        print("缓存重新生成完成！")
    
    sys.exit(0)

# 不再每次重启都清理缓存，只在明确需要时（如配置变更）才清理
# image_processor.clean_all_cache()

# 可选：只在配置发生变更时清理缓存
# config_changes = config.check_config_changes()
# if config_changes['thumbnail_changed'] or config_changes['preview_changed']:
#     print("检测到配置变更，正在清理缓存...")
#     image_processor.clean_all_cache()
#     print("缓存清理完成！")

def login_required(f):
    """登录验证装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return jsonify({'error': '需要登录'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    """主页"""
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login():
    """用户登录"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if config.verify_user(username, password):
        session.permanent = True  # 必须在设置session数据之前设置
        session['username'] = username
        user_info = config.config['users'][username]
        return jsonify({
            'success': True,
            'user': {
                'username': username,
                'role': user_info['role']
            }
        })
    else:
        return jsonify({'error': '用户名或密码错误'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    """用户登出"""
    session.pop('username', None)
    return jsonify({'success': True})

@app.route('/api/auth/status')
def auth_status():
    """检查登录状态"""
    if 'username' in session:
        username = session['username']
        user_info = config.config['users'].get(username)
        if user_info:
            return jsonify({
                'authenticated': True,
                'user': {
                    'username': username,
                    'role': user_info['role']
                }
            })
    return jsonify({'authenticated': False}), 401

@app.route('/api/directories')
@login_required
def get_directories():
    """获取用户可访问的目录列表"""
    username = session['username']
    accessible_dirs = config.get_user_accessible_dirs(username)
    
    directories = []
    for dir_path in accessible_dirs:
        if os.path.exists(dir_path):
            directories.append({
                'path': dir_path,
                'name': os.path.basename(dir_path)
            })
    
    return jsonify(directories)

@app.route('/api/browse')
@login_required
def browse_directory():
    """浏览目录，获取子文件夹和图片列表"""
    directory = request.args.get('directory')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    sort_by = request.args.get('sort_by', 'name')  # name, date, rating, modified
    sort_order = request.args.get('sort_order', 'asc')  # asc, desc
    
    username = session['username']
    accessible_dirs = config.get_user_accessible_dirs(username)
    
    # 检查是否有权限访问此目录
    has_permission = False
    for accessible_dir in accessible_dirs:
        if directory.startswith(accessible_dir):
            has_permission = True
            break
    
    if not has_permission:
        return jsonify({'error': '无权访问此目录'}), 403
    
    if not os.path.exists(directory):
        return jsonify({'error': '目录不存在'}), 404
    
    # 获取子文件夹
    subdirectories = []
    try:
        for item in os.listdir(directory):
            if item.startswith('.'):  # 跳过隐藏文件夹
                continue
            item_path = os.path.join(directory, item)
            if os.path.isdir(item_path):
                # 获取文件夹中的图片数量和预览图片
                folder_images = image_processor.scan_current_directory(item_path)
                image_count = len(folder_images)
                preview_image = folder_images[0] if folder_images else None
                
                # 如果当前目录没有图片，递归查找子目录中的图片作为预览图
                if not preview_image:
                    preview_image = image_processor.find_preview_image_in_subdirectories(item_path)
                
                subdirectories.append({
                    'name': item,
                    'path': item_path,
                    'type': 'directory',
                    'image_count': image_count,
                    'preview_image': preview_image
                })
    except PermissionError:
        pass
    
    # 扫描当前目录获取图片（不递归）
    images = image_processor.scan_current_directory(directory)
    
    # 排序
    if sort_by == 'name':
        images.sort(key=lambda x: x['metadata']['filename'], reverse=(sort_order == 'desc'))
    elif sort_by == 'date':
        images.sort(key=lambda x: x['metadata'].get('exif', {}).get('DateTime', ''), reverse=(sort_order == 'desc'))
    elif sort_by == 'rating':
        images.sort(key=lambda x: x['metadata']['rating'], reverse=(sort_order == 'desc'))
    elif sort_by == 'modified':
        images.sort(key=lambda x: x['metadata']['modified_time'], reverse=(sort_order == 'desc'))
    
    # 分页
    total = len(images)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_images = images[start:end]
    
    return jsonify({
        'subdirectories': subdirectories,
        'images': paginated_images,
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': (total + per_page - 1) // per_page,
        'current_directory': directory
    })

@app.route('/api/images')
@login_required
def get_images():
    """获取指定目录的图片列表（保持向后兼容）"""
    return browse_directory()

@app.route('/api/image/thumbnail')
def get_thumbnail():
    """获取缩略图"""
    file_path = request.args.get('file_path')
    if not file_path:
        return jsonify({'error': '缺少文件路径参数'}), 400
    
    username = session.get('username')
    if not username:
        return jsonify({'error': '需要登录'}), 401
    
    # 检查权限
    accessible_dirs = config.get_user_accessible_dirs(username)
    file_accessible = any(file_path.startswith(dir_path) for dir_path in accessible_dirs)
    
    if not file_accessible:
        return jsonify({'error': '无权访问此文件'}), 403
    
    # 生成或获取缩略图
    thumbnail_path = image_processor.generate_thumbnail(file_path)
    if thumbnail_path and os.path.exists(thumbnail_path):
        return send_file(thumbnail_path, mimetype='image/jpeg')
    else:
        return jsonify({'error': '缩略图不存在'}), 404

@app.route('/api/image/preview')
def get_preview():
    """获取预览大图
    
    如果预览图不存在，会将其添加到优先级队列中优先处理
    返回正在生成状态，让客户端可以稍后重试
    """
    file_path = request.args.get('file_path')
    if not file_path:
        return jsonify({'error': '缺少文件路径参数'}), 400
    
    username = session.get('username')
    if not username:
        return jsonify({'error': '需要登录'}), 401
    
    # 检查权限
    accessible_dirs = config.get_user_accessible_dirs(username)
    file_accessible = any(file_path.startswith(dir_path) for dir_path in accessible_dirs)
    
    if not file_accessible:
        return jsonify({'error': '无权访问此文件'}), 403
    
    # 首先检查预览图是否已存在
    cache_dir = image_processor.get_cache_dir(file_path)
    file_hash = image_processor.get_file_hash(file_path)
    preview_path = os.path.join(cache_dir, f"preview_{file_hash}.jpg")
    
    if os.path.exists(preview_path):
        # 预览图已存在，直接返回
        return send_file(preview_path, mimetype='image/jpeg')
    else:
        # 预览图不存在，将其添加到优先级队列中优先处理
        success = image_processor.prioritize_preview(file_path)
        
        if success:
            # 返回正在生成状态，客户端可以稍后重试
            return jsonify({'status': 'generating', 'message': '预览图正在生成中，请稍候重试'}), 202
        else:
            # 优先处理失败，返回错误
            return jsonify({'error': '预览图生成失败'}), 500

@app.route('/api/image/download')
@login_required
def download_original():
    """下载原图"""
    file_path = request.args.get('file_path')
    username = session['username']
    accessible_dirs = config.get_user_accessible_dirs(username)
    
    # 检查文件是否在用户可访问的目录中
    file_accessible = False
    for dir_path in accessible_dirs:
        if file_path.startswith(dir_path):
            file_accessible = True
            break
    
    if not file_accessible:
        return jsonify({'error': '无权访问此文件'}), 403
    
    if not os.path.exists(file_path):
        return jsonify({'error': '文件不存在'}), 404
    
    return send_file(file_path, as_attachment=True)

@app.route('/api/image/metadata')
@login_required
def get_metadata():
    """获取图片元数据"""
    file_path = request.args.get('file_path')
    username = session['username']
    accessible_dirs = config.get_user_accessible_dirs(username)
    
    # 检查权限
    file_accessible = False
    for dir_path in accessible_dirs:
        if file_path.startswith(dir_path):
            file_accessible = True
            break
    
    if not file_accessible:
        return jsonify({'error': '无权访问此文件'}), 403
    
    metadata = image_processor.extract_metadata(file_path)
    return jsonify(metadata)

@app.route('/api/image/rating', methods=['POST'])
@login_required
def set_rating():
    """设置图片星级"""
    data = request.get_json()
    file_path = data.get('file_path')
    rating = data.get('rating', 0)
    
    username = session['username']
    accessible_dirs = config.get_user_accessible_dirs(username)
    
    # 检查权限
    file_accessible = False
    for dir_path in accessible_dirs:
        if file_path.startswith(dir_path):
            file_accessible = True
            break
    
    if not file_accessible:
        return jsonify({'error': '无权访问此文件'}), 403
    
    success = image_processor.set_windows_rating(file_path, rating)
    
    if success:
        # 更新缓存的元数据
        cache_dir = image_processor.get_cache_dir(file_path)
        file_hash = image_processor.get_file_hash(file_path)
        metadata_path = os.path.join(cache_dir, f"meta_{file_hash}.json")
        
        try:
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                metadata['rating'] = rating
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"更新元数据缓存失败: {e}")
        
        return jsonify({'success': True})
    else:
        return jsonify({'error': '设置星级失败'}), 500

@app.route('/api/admin/directories', methods=['POST'])
@login_required
def add_directory():
    """添加图片目录（管理员功能）"""
    username = session['username']
    user_info = config.config['users'][username]
    
    if user_info['role'] != 'admin':
        return jsonify({'error': '需要管理员权限'}), 403
    
    data = request.get_json()
    directory = data.get('directory')
    
    if not os.path.exists(directory):
        return jsonify({'error': '目录不存在'}), 404
    
    config.add_image_directory(directory)
    return jsonify({'success': True})

@app.route('/api/admin/users', methods=['POST'])
@login_required
def add_user():
    """添加用户（管理员功能）"""
    username = session['username']
    user_info = config.config['users'][username]
    
    if user_info['role'] != 'admin':
        return jsonify({'error': '需要管理员权限'}), 403
    
    data = request.get_json()
    new_username = data.get('username')
    password = data.get('password')
    accessible_dirs = data.get('accessible_dirs', [])
    
    config.add_user(new_username, password, accessible_dirs)
    return jsonify({'success': True})

@app.route('/api/admin/clean_thumbnails', methods=['POST'])
@login_required
def clean_thumbnails():
    """清理所有缩略图（管理员功能）"""
    username = session['username']
    user_info = config.config['users'][username]
    
    if user_info['role'] != 'admin':
        return jsonify({'error': '需要管理员权限'}), 403
    
    try:
        image_processor.clean_all_thumbnails()
        return jsonify({'success': True, 'message': '所有缩略图已清理完成'})
    except Exception as e:
        return jsonify({'error': f'清理缩略图失败: {str(e)}'}), 500

if __name__ == '__main__':
    # 创建模板目录
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static', exist_ok=True)
    
    server_config = config.config['server']
    app.run(
        host=server_config['host'],
        port=server_config['port'],
        debug=server_config['debug']
    )
