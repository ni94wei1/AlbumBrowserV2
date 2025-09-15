from flask import Flask, request, jsonify, send_file, render_template, session
from flask_cors import CORS
import os
import json
from config import Config
from image_processor import ImageProcessor
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # 在生产环境中应该使用更安全的密钥
CORS(app)

# 初始化配置和图片处理器
config = Config()
image_processor = ImageProcessor(config)

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

@app.route('/api/images')
@login_required
def get_images():
    """获取指定目录的图片列表"""
    directory = request.args.get('directory')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))
    sort_by = request.args.get('sort_by', 'name')  # name, date, rating, modified
    sort_order = request.args.get('sort_order', 'asc')  # asc, desc
    
    username = session['username']
    accessible_dirs = config.get_user_accessible_dirs(username)
    
    if directory not in accessible_dirs:
        return jsonify({'error': '无权访问此目录'}), 403
    
    if not os.path.exists(directory):
        return jsonify({'error': '目录不存在'}), 404
    
    # 扫描目录获取图片
    images = image_processor.scan_directory(directory)
    
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
        'images': paginated_images,
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': (total + per_page - 1) // per_page
    })

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
    """获取预览大图"""
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
    
    # 生成或获取预览图
    preview_path = image_processor.generate_preview(file_path)
    if preview_path and os.path.exists(preview_path):
        return send_file(preview_path, mimetype='image/jpeg')
    else:
        return jsonify({'error': '预览图不存在'}), 404

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
        file_hash = image_processor.get_file_hash(file_path)
        metadata_path = os.path.join(image_processor.metadata_dir, f"{file_hash}.json")
        
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
