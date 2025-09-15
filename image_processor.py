import os
import json
import hashlib
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
        self.cache_dir = 'cache'
        self.thumbnails_dir = os.path.join(self.cache_dir, 'thumbnails')
        self.previews_dir = os.path.join(self.cache_dir, 'previews')
        self.metadata_dir = os.path.join(self.cache_dir, 'metadata')
        
        # 创建缓存目录
        for dir_path in [self.cache_dir, self.thumbnails_dir, self.previews_dir, self.metadata_dir]:
            os.makedirs(dir_path, exist_ok=True)
    
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
        """生成缩略图"""
        file_hash = self.get_file_hash(file_path)
        thumbnail_path = os.path.join(self.thumbnails_dir, f"{file_hash}.jpg")
        
        if os.path.exists(thumbnail_path):
            return thumbnail_path
        
        try:
            image = self.load_image(file_path)
            if not image:
                return None
            
            # 生成正方形缩略图
            size = self.config.config['thumbnail_size']
            image.thumbnail(size, Image.Resampling.LANCZOS)
            
            # 创建正方形画布
            thumbnail = Image.new('RGB', size, (255, 255, 255))
            
            # 居中粘贴
            x = (size[0] - image.width) // 2
            y = (size[1] - image.height) // 2
            thumbnail.paste(image, (x, y))
            
            thumbnail.save(thumbnail_path, 'JPEG', quality=85)
            return thumbnail_path
            
        except Exception as e:
            print(f"生成缩略图失败 {file_path}: {e}")
            return None
    
    def generate_preview(self, file_path: str) -> Optional[str]:
        """生成预览大图"""
        file_hash = self.get_file_hash(file_path)
        preview_path = os.path.join(self.previews_dir, f"{file_hash}.jpg")
        
        if os.path.exists(preview_path):
            return preview_path
        
        try:
            image = self.load_image(file_path)
            if not image:
                return None
            
            # 按比例缩放，最大边不超过指定尺寸
            max_size = self.config.config['preview_max_size']
            image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            image.save(preview_path, 'JPEG', quality=90)
            return preview_path
            
        except Exception as e:
            print(f"生成预览图失败 {file_path}: {e}")
            return None
    
    def extract_metadata(self, file_path: str) -> Dict:
        """提取图片元数据"""
        file_hash = self.get_file_hash(file_path)
        metadata_path = os.path.join(self.metadata_dir, f"{file_hash}.json")
        
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
                        metadata['exif'][tag] = str(value)
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
            for file in files:
                file_path = os.path.join(root, file)
                
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
