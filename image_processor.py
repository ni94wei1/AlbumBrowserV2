import os
import json
import hashlib
import shutil
from PIL import Image, ExifTags
from PIL.ExifTags import TAGS
import exifread
from typing import Dict, List, Tuple, Optional

# RAW支持暂时禁用，避免兼容性问题
RAWPY_AVAILABLE = False

try:
    import win32file
    import win32con
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False
    print("警告: pywin32未安装，Windows星级评分功能将被禁用")

class ImageProcessor:
    def __init__(self, config):
        self.config = config
        # 不再使用统一的cache目录，改为在图片原目录下生成隐藏文件夹
    
    def get_cache_dir(self, file_path: str) -> str:
        """获取图片文件对应的缓存目录"""
        image_dir = os.path.dirname(file_path)
        cache_dir = os.path.join(image_dir, '.album_cache')
        os.makedirs(cache_dir, exist_ok=True)
        return cache_dir
    
    def get_file_hash(self, file_path: str) -> str:
        """获取文件哈希值作为缓存键"""
        stat = os.stat(file_path)
        content = f"{file_path}_{stat.st_mtime}_{stat.st_size}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def is_supported_format(self, file_path: str) -> bool:
        """检查是否为支持的图片格式"""
        ext = os.path.splitext(file_path)[1].lower()
        return ext in self.config.config['supported_formats']
    
    def is_raw_format(self, file_path: str) -> bool:
        """检查是否为RAW格式"""
        ext = os.path.splitext(file_path)[1].lower()
        raw_formats = ['.raw', '.cr2', '.nef', '.arw', '.dng', '.orf', '.rw2']
        return ext in raw_formats
    
    def load_image(self, file_path: str) -> Optional[Image.Image]:
        """加载图片，支持RAW格式"""
        try:
            if self.is_raw_format(file_path):
                print(f"RAW文件暂不支持: {file_path}")
                return None
            else:
                return Image.open(file_path)
        except Exception as e:
            print(f"加载图片失败 {file_path}: {e}")
            return None
    
    def generate_thumbnail(self, file_path: str) -> Optional[str]:
        """生成缩略图（裁剪为正方形）"""
        cache_dir = self.get_cache_dir(file_path)
        file_hash = self.get_file_hash(file_path)
        thumbnail_path = os.path.join(cache_dir, f"thumb_{file_hash}.jpg")
        
        if os.path.exists(thumbnail_path):
            return thumbnail_path
        
        try:
            image = self.load_image(file_path)
            if not image:
                return None
            
            # 生成正方形缩略图（裁剪方式）
            size = self.config.config['thumbnail_size'][0]  # 使用正方形
            
            # 计算裁剪区域（居中裁剪）
            width, height = image.size
            if width > height:
                # 宽图，裁剪左右
                left = (width - height) // 2
                top = 0
                right = left + height
                bottom = height
            else:
                # 高图，裁剪上下
                left = 0
                top = (height - width) // 2
                right = width
                bottom = top + width
            
            # 裁剪为正方形
            cropped = image.crop((left, top, right, bottom))
            
            # 缩放到目标尺寸
            thumbnail = cropped.resize((size, size), Image.Resampling.LANCZOS)
            
            # 处理透明通道，转换为RGB模式
            if thumbnail.mode in ('RGBA', 'LA', 'P'):
                # 创建白色背景
                background = Image.new('RGB', thumbnail.size, (255, 255, 255))
                if thumbnail.mode == 'P':
                    thumbnail = thumbnail.convert('RGBA')
                background.paste(thumbnail, mask=thumbnail.split()[-1] if thumbnail.mode == 'RGBA' else None)
                thumbnail = background
            elif thumbnail.mode != 'RGB':
                thumbnail = thumbnail.convert('RGB')
            
            thumbnail_quality = self.config.config.get('thumbnail_quality', 70)
            thumbnail.save(thumbnail_path, 'JPEG', quality=thumbnail_quality, optimize=True, progressive=True)
            return thumbnail_path
            
        except Exception as e:
            print(f"生成缩略图失败 {file_path}: {e}")
            return None
    
    def generate_preview(self, file_path: str) -> Optional[str]:
        """生成预览大图"""
        cache_dir = self.get_cache_dir(file_path)
        file_hash = self.get_file_hash(file_path)
        preview_path = os.path.join(cache_dir, f"preview_{file_hash}.jpg")
        
        if os.path.exists(preview_path):
            return preview_path
        
        try:
            image = self.load_image(file_path)
            if not image:
                return None
            
            # 按比例缩放，最大边不超过指定尺寸
            max_size = self.config.config['preview_max_size']
            image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            # 处理透明通道，转换为RGB模式
            if image.mode in ('RGBA', 'LA', 'P'):
                # 创建白色背景
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            preview_quality = self.config.config.get('preview_quality', 75)
            image.save(preview_path, 'JPEG', quality=preview_quality, optimize=True, progressive=True)
            return preview_path
            
        except Exception as e:
            print(f"生成预览图失败 {file_path}: {e}")
            return None
    
    def extract_metadata(self, file_path: str) -> Dict:
        """提取图片元数据"""
        cache_dir = self.get_cache_dir(file_path)
        file_hash = self.get_file_hash(file_path)
        metadata_path = os.path.join(cache_dir, f"meta_{file_hash}.json")
        
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        
        metadata = {
            'filename': os.path.basename(file_path),
            'file_size': os.path.getsize(file_path),
            'modified_time': os.path.getmtime(file_path),
            'rating': self.get_windows_rating(file_path),
            'exif': {}
        }
        
        try:
            # 提取EXIF信息
            if not self.is_raw_format(file_path):
                image = Image.open(file_path)
                exif_dict = image._getexif()
                
                if exif_dict:
                    for tag_id, value in exif_dict.items():
                        tag = TAGS.get(tag_id, tag_id)
                        # 确保所有值都可以序列化
                        try:
                            metadata['exif'][str(tag)] = str(value)
                        except (TypeError, ValueError):
                            metadata['exif'][str(tag)] = 'N/A'
            else:
                # RAW文件使用exifread
                with open(file_path, 'rb') as f:
                    tags = exifread.process_file(f)
                    for tag in tags.keys():
                        if tag not in ['JPEGThumbnail', 'TIFFThumbnail', 'Filename', 'EXIF MakerNote']:
                            metadata['exif'][tag] = str(tags[tag])
            
            # 保存元数据缓存
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            print(f"提取元数据失败 {file_path}: {e}")
        
        return metadata
    
    def clean_old_cache(self):
        """清理项目目录下的旧缓存文件"""
        project_cache_dir = 'cache'
        if os.path.exists(project_cache_dir):
            try:
                shutil.rmtree(project_cache_dir)
                print(f"已删除旧缓存目录: {project_cache_dir}")
            except Exception as e:
                print(f"删除旧缓存目录失败: {e}")
    
    def clean_all_cache(self):
        """清理所有图片目录下的缓存文件"""
        cleaned_count = 0
        for directory in self.config.config['image_directories']:
            if os.path.exists(directory):
                for root, dirs, files in os.walk(directory):
                    if '.album_cache' in dirs:
                        cache_path = os.path.join(root, '.album_cache')
                        try:
                            shutil.rmtree(cache_path)
                            cleaned_count += 1
                            print(f"已删除缓存目录: {cache_path}")
                        except Exception as e:
                            print(f"删除缓存目录失败 {cache_path}: {e}")
        print(f"总共清理了 {cleaned_count} 个缓存目录")
    
    def get_windows_rating(self, file_path: str) -> int:
        """获取Windows文件星级评分"""
        if not WIN32_AVAILABLE:
            return 0
        try:
            # 使用Windows API获取文件属性
            handle = win32file.CreateFile(
                file_path,
                win32con.GENERIC_READ,
                win32con.FILE_SHARE_READ,
                None,
                win32con.OPEN_EXISTING,
                0,
                None
            )
            # 这里需要实现获取星级的逻辑
            # Windows的星级存储在文件的扩展属性中
            win32file.CloseHandle(handle)
            return 0  # 暂时返回0，后续实现
        except:
            return 0
    
    def set_windows_rating(self, file_path: str, rating: int) -> bool:
        """设置Windows文件星级评分"""
        if not WIN32_AVAILABLE:
            return False
        try:
            # 这里需要实现设置星级的逻辑
            # Windows的星级需要通过COM接口或者直接操作NTFS流来设置
            return True
        except Exception as e:
            print(f"设置星级失败 {file_path}: {e}")
            return False
    
    def scan_directory(self, directory: str) -> List[Dict]:
        """扫描目录中的图片文件"""
        images = []
        
        for root, dirs, files in os.walk(directory):
            # 排除以.开头的隐藏目录，避免扫描缓存文件夹
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for file in files:
                file_path = os.path.join(root, file)
                
                # 跳过隐藏文件夹中的文件
                if '.album_cache' in file_path or any(part.startswith('.') for part in file_path.split(os.sep)):
                    continue
                
                if self.is_supported_format(file_path):
                    # 检查是否有同名的JPG和RAW文件
                    base_name = os.path.splitext(file_path)[0]
                    jpg_path = None
                    raw_path = None
                    
                    # 查找同名文件
                    for ext in ['.jpg', '.jpeg']:
                        potential_jpg = base_name + ext
                        if os.path.exists(potential_jpg):
                            jpg_path = potential_jpg
                            break
                    
                    if self.is_raw_format(file_path):
                        raw_path = file_path
                    
                    # 根据规则决定显示哪个文件
                    display_path = file_path
                    if jpg_path and raw_path:
                        display_path = jpg_path  # 优先显示JPG
                    elif jpg_path:
                        display_path = jpg_path
                    elif raw_path:
                        display_path = raw_path
                    
                    # 避免重复添加
                    if not any(img['file_path'] == display_path for img in images):
                        metadata = self.extract_metadata(display_path)
                        
                        image_info = {
                            'file_path': display_path,
                            'relative_path': os.path.relpath(display_path, directory),
                            'thumbnail_path': self.generate_thumbnail(display_path),
                            'preview_path': self.generate_preview(display_path),
                            'metadata': metadata,
                            'has_raw': raw_path is not None,
                            'has_jpg': jpg_path is not None
                        }
                        
                        images.append(image_info)
        
        return images
    
    def scan_current_directory(self, directory: str) -> List[Dict]:
        """扫描当前目录中的图片文件（不递归子目录）"""
        images = []
        
        try:
            for file in os.listdir(directory):
                if file.startswith('.'):  # 跳过隐藏文件
                    continue
                    
                file_path = os.path.join(directory, file)
                
                # 只处理文件，不处理目录
                if not os.path.isfile(file_path):
                    continue
                
                if self.is_supported_format(file_path):
                    # 检查是否有同名的JPG和RAW文件
                    base_name = os.path.splitext(file_path)[0]
                    jpg_path = None
                    raw_path = None
                    
                    # 查找同名文件
                    for ext in ['.jpg', '.jpeg']:
                        potential_jpg = base_name + ext
                        if os.path.exists(potential_jpg):
                            jpg_path = potential_jpg
                            break
                    
                    if self.is_raw_format(file_path):
                        raw_path = file_path
                    
                    # 根据规则决定显示哪个文件
                    display_path = file_path
                    if jpg_path and raw_path:
                        display_path = jpg_path  # 优先显示JPG
                    elif jpg_path:
                        display_path = jpg_path
                    elif raw_path:
                        display_path = raw_path
                    
                    # 避免重复添加
                    if not any(img['file_path'] == display_path for img in images):
                        metadata = self.extract_metadata(display_path)
                        
                        image_info = {
                            'file_path': display_path,
                            'relative_path': os.path.relpath(display_path, directory),
                            'thumbnail_path': self.generate_thumbnail(display_path),
                            'preview_path': self.generate_preview(display_path),
                            'metadata': metadata,
                            'has_raw': raw_path is not None,
                            'has_jpg': jpg_path is not None
                        }
                        
                        images.append(image_info)
        except PermissionError:
            print(f"权限不足，无法访问目录: {directory}")
        except Exception as e:
            print(f"扫描目录失败 {directory}: {e}")
        
        return images
