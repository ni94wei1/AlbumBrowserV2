import os
import json
import hashlib
import shutil
import os
import tempfile
from PIL import Image, ExifTags, ImageDraw, ImageFont
from PIL.ExifTags import TAGS
import exifread
from typing import Dict, List, Tuple, Optional

# 暂时禁用rawpy依赖，使用替代方法处理RAW文件
RAWPY_AVAILABLE = False

# 尝试导入win32file和win32con用于Windows星级评分功能
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
        # 扩展RAW格式列表以支持更多类型，包括Canon的CR3格式
        raw_formats = ['.raw', '.cr2', '.cr3', '.nef', '.arw', '.dng', '.orf', '.rw2',
                      '.crw', '.mrw', '.pef', '.raf', '.sr2', '.srf', '.x3f',
                      '.tif', '.tiff', '.dcr', '.kdc', '.mos', '.erf']
        result = ext in raw_formats
        print(f"检查文件格式: {file_path}, 扩展名: {ext}, 是否RAW: {result}")
        return result
    
    def load_image(self, file_path: str) -> Optional[Image.Image]:
        """加载图片，支持RAW格式"""
        try:
            if self.is_raw_format(file_path):
                # 对于RAW文件，我们无法直接加载为PIL Image，但可以使用EXIF方向信息
                # 注意：实际的RAW文件加载需要rawpy，但由于兼容性问题，我们暂时返回None
                # 但在缩略图和预览图生成时会特殊处理RAW文件的方向
                return None
            else:
                return Image.open(file_path)
        except Exception as e:
            print(f"加载图片失败 {file_path}: {e}")
            return None

    def _process_raw_file_for_preview(self, file_path: str, file_hash: str, cache_dir: str) -> Optional[Image.Image]:
        """统一处理RAW文件的预览图提取，增强了对Canon CR3格式的支持"""
        try:
            # 获取文件信息
            file_extension = os.path.splitext(file_path)[1].lower()
            file_size = os.path.getsize(file_path) / 1024 / 1024  # MB
            print(f"处理RAW文件: {file_path}")
            print(f"  文件扩展名: {file_extension}")
            print(f"  文件大小: {file_size:.2f} MB")
            
            # 尝试使用多种方法提取缩略图
            temp_image_path = None
            
            # 1. 尝试使用exifread库提取缩略图（适用于大多数RAW格式）
            try:
                # 对于Canon CR3格式的特殊处理
                if file_extension == '.cr3':
                    print(f"  这是Canon CR3格式文件")
                    
                    # 方法1: 尝试直接从文件读取嵌入的JPEG数据
                    # CR3文件通常在文件开头或特定位置包含JPEG预览图
                    with open(file_path, 'rb') as f:
                        file_data = f.read()
                        
                        # 查找JPEG文件的开始标记(0xFFD8)和结束标记(0xFFD9)
                        # 尝试寻找多个可能的JPEG片段，选择尺寸最大的那个
                        jpeg_starts = []
                        pos = 0
                        while True:
                            pos = file_data.find(b'\xff\xd8', pos)
                            if pos == -1:
                                break
                            jpeg_starts.append(pos)
                            pos += 1
                        
                        best_jpeg_data = None
                        best_jpeg_size = 0
                        
                        for jpeg_start in jpeg_starts:
                            jpeg_end = file_data.find(b'\xff\xd9', jpeg_start)
                            if jpeg_end != -1:
                                jpeg_data_candidate = file_data[jpeg_start:jpeg_end+2]
                                jpeg_size = len(jpeg_data_candidate)
                                
                                # 选择最大的JPEG数据块（通常是高质量预览图）
                                if jpeg_size > best_jpeg_size:
                                    best_jpeg_size = jpeg_size
                                    best_jpeg_data = jpeg_data_candidate
                        
                        if best_jpeg_data:
                            # 保存提取的JPEG数据到临时文件
                            temp_image_path = os.path.join(cache_dir, f"temp_thumb_preview_{file_hash}.jpg")
                            with open(temp_image_path, 'wb') as jpeg_file:
                                jpeg_file.write(best_jpeg_data)
                            print(f"  成功提取CR3嵌入JPEG预览图，大小: {best_jpeg_size} 字节")
                        else:
                            print(f"  未找到有效JPEG数据")
            except Exception as e:
                print(f"  提取缩略图时出错: {str(e)}")
            
            # 如果未能提取到缩略图，创建一个占位图
            if not temp_image_path:
                print(f"  尝试生成一个表示RAW文件的占位图")
                # 创建一个表示RAW文件的占位图
                placeholder_size = 300  # 默认占位图尺寸
                placeholder = Image.new('RGB', (placeholder_size, placeholder_size), color='gray')
                draw = ImageDraw.Draw(placeholder)
                text = "RAW\n文件"
                font = ImageFont.load_default()
                
                # 计算文本位置使其居中
                text_bbox = draw.textbbox((0, 0), text, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]
                position = ((placeholder_size - text_width) // 2, (placeholder_size - text_height) // 2)
                
                # 在占位图上绘制文本
                draw.text(position, text, fill='white', font=font)
                
                # 保存占位图
                temp_image_path = os.path.join(cache_dir, f"temp_thumb_preview_{file_hash}.jpg")
                placeholder.save(temp_image_path, 'JPEG', quality=85)
                print(f"  已创建RAW文件占位图")
            
            # 加载临时文件并处理
            if temp_image_path and os.path.exists(temp_image_path):
                image = Image.open(temp_image_path)
                
                # 检查是否是横屏图片，如果是则旋转90度使其成为竖屏
                img_width, img_height = image.size
                if img_width > img_height:
                    print(f"  检测到横屏RAW图片({img_width}x{img_height})，强制旋转为竖屏")
                    image = image.rotate(90, expand=True)
                
                # 尝试修复方向
                image = self.fix_image_orientation(image)
                
                # 清理临时文件
                try:
                    os.remove(temp_image_path)
                except:
                    pass
                
                return image
            else:
                print(f"  未能创建临时图像文件")
                return None
            
        except Exception as e:
            print(f"处理RAW文件时发生错误: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def _resize_and_save_image(self, image: Image.Image, output_path: str, max_width: int, max_height: int, quality: int) -> bool:
        """统一处理图片的缩放和保存"""
        try:
            # 计算缩放比例
            img_width, img_height = image.size
            aspect_ratio = img_width / img_height
            print(f"  原始尺寸: {img_width}x{img_height}, 宽高比: {aspect_ratio:.2f}")
            
            # 根据宽高比例调整最终尺寸
            if max_width > 0 and max_height == 0:
                # 只限制宽度，高度按比例缩放
                new_width = min(max_width, img_width)
                new_height = int(new_width / aspect_ratio)
            elif max_height > 0 and max_width == 0:
                # 只限制高度，宽度按比例缩放
                new_height = min(max_height, img_height)
                new_width = int(new_height * aspect_ratio)
            else:
                # 限制宽高，按原比例缩放
                if aspect_ratio > 1:  # 横屏图片
                    new_width = min(max_width, img_width)
                    new_height = int(new_width / aspect_ratio)
                else:  # 竖屏图片
                    new_height = min(max_height, img_height)
                    new_width = int(new_height * aspect_ratio)
            print(f"  调整后尺寸: {new_width}x{new_height}")
            
            # 使用resize而不是thumbnail，以确保精确控制尺寸
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
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
            
            # 保存图片
            image.save(output_path, 'JPEG', quality=quality, optimize=True, progressive=True)
            print(f"  成功保存到: {output_path}")
            return True
        except Exception as e:
            print(f"缩放和保存图片失败 {output_path}: {e}")
            return False

    def generate_thumbnail(self, file_path: str) -> Optional[str]:
        """生成缩略图（保持原比例，根据配置和图片方向智能计算尺寸）"""
        cache_dir = self.get_cache_dir(file_path)
        file_hash = self.get_file_hash(file_path)
        thumbnail_path = os.path.join(cache_dir, f"thumb_{file_hash}.jpg")
        
        if os.path.exists(thumbnail_path):
            return thumbnail_path
        
        try:
            # 对于RAW文件的特殊处理
            if self.is_raw_format(file_path):
                # 使用统一的RAW文件处理方法
                image = self._process_raw_file_for_preview(file_path, file_hash, cache_dir)
                if image:
                    # 获取配置的缩略图尺寸，默认为[300, 0]
                    thumbnail_size = self.config.config.get('thumbnail_size', [300, 0])
                    max_width, max_height = thumbnail_size
                    thumbnail_quality = self.config.config.get('thumbnail_quality', 70)
                    
                    # 检查提取的图片尺寸，如果太小则进行适当放大
                    img_width, img_height = image.size
                    if img_width < 200 or img_height < 200:
                        print(f"  检测到小尺寸图片({img_width}x{img_height})，将进行适当放大")
                        # 强制放大到合理尺寸，但不超过配置的最大值
                        scale_factor = 2  # 放大倍数
                        if max_width > 0:
                            new_width = min(max_width, int(img_width * scale_factor))
                        else:
                            new_width = int(img_width * scale_factor)
                        if max_height > 0:
                            new_height = min(max_height, int(img_height * scale_factor))
                        else:
                            new_height = int(img_height * scale_factor)
                        
                        # 使用LANCZOS滤镜进行高质量放大
                        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        print(f"  放大后尺寸: {new_width}x{new_height}")
                    
                    if self._resize_and_save_image(image, thumbnail_path, max_width, max_height, thumbnail_quality):
                        return thumbnail_path
                # 如果无法提取预览图，返回None
                return None
            
            # 非RAW文件的标准处理
            image = self.load_image(file_path)
            if not image:
                return None
            
            # 处理EXIF方向信息
            image = self.fix_image_orientation(image)
            
            # 获取配置的缩略图尺寸
            thumbnail_size = self.config.config.get('thumbnail_size', [300, 0])
            width, height = thumbnail_size
            
            # 计算缩放比例
            img_width, img_height = image.size
            aspect_ratio = img_width / img_height
            
            # 根据宽高比例调整最终尺寸
            if width > 0 and height == 0:
                # 只限制宽度，高度按比例缩放
                new_width = min(width, img_width)
                new_height = int(new_width / aspect_ratio)
            elif height > 0 and width == 0:
                # 只限制高度，宽度按比例缩放
                new_height = min(height, img_height)
                new_width = int(new_height * aspect_ratio)
            else:
                # 限制宽高，按原比例缩放
                if aspect_ratio > 1:  # 横屏图片
                    new_width = min(width, img_width)
                    new_height = int(new_width / aspect_ratio)
                else:  # 竖屏图片
                    new_height = min(height, img_height)
                    new_width = int(new_height * aspect_ratio)
            
            # 使用resize而不是thumbnail，以确保精确控制尺寸
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
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
            
            thumbnail_quality = self.config.config.get('thumbnail_quality', 70)
            image.save(thumbnail_path, 'JPEG', quality=thumbnail_quality, optimize=True, progressive=True)
            return thumbnail_path
            
        except Exception as e:
            print(f"生成缩略图失败 {file_path}: {e}")
            return None
    
    def generate_preview(self, file_path: str) -> Optional[str]:
        """生成预览大图（保持原比例，根据配置和图片方向智能计算尺寸）"""
        cache_dir = self.get_cache_dir(file_path)
        file_hash = self.get_file_hash(file_path)
        preview_path = os.path.join(cache_dir, f"preview_{file_hash}.jpg")
        
        if os.path.exists(preview_path):
            return preview_path
        
        try:
            # 对于RAW文件的特殊处理
            if self.is_raw_format(file_path):
                # 使用统一的RAW文件处理方法
                image = self._process_raw_file_for_preview(file_path, file_hash, cache_dir)
                if image:
                    max_size = self.config.config['preview_max_size']
                    preview_quality = self.config.config.get('preview_quality', 75)
                    
                    # 对于预览图，保持较大的尺寸
                    if self._resize_and_save_image(image, preview_path, max_size, 0, preview_quality):
                        return preview_path
                # 如果无法提取预览图，返回None
                return None
            
            # 非RAW文件的标准处理
            image = self.load_image(file_path)
            if not image:
                return None
            
            # 处理EXIF方向信息
            image = self.fix_image_orientation(image)
            
            # 获取配置的预览图最大尺寸
            max_size = self.config.config['preview_max_size']
            
            # 计算缩放比例
            img_width, img_height = image.size
            aspect_ratio = img_width / img_height
            
            # 根据宽高比例调整最终尺寸
            if aspect_ratio > 1:  # 横屏图片
                new_width = min(max_size, img_width)
                new_height = int(new_width / aspect_ratio)
            else:  # 竖屏图片
                new_height = min(max_size, img_height)
                new_width = int(new_height * aspect_ratio)
            
            # 使用resize而不是thumbnail，以确保精确控制尺寸
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
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
            except Exception as e:
                print(f"加载缓存的元数据失败 {file_path}: {e}")
        
        metadata = {
            'filename': os.path.basename(file_path),
            'file_size': os.path.getsize(file_path),
            'modified_time': os.path.getmtime(file_path),
            'rating': self.get_windows_rating(file_path),
            'exif': {},
            'is_raw': self.is_raw_format(file_path)
        }
        
        try:
            # 提取EXIF信息
            if not metadata['is_raw']:
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
                file_ext = os.path.splitext(file_path)[1].lower()
                print(f"尝试提取RAW文件元数据: {file_path}")
                print(f"  文件扩展名: {file_ext}")
                
                # 添加RAW文件特定信息
                metadata['file_format'] = file_ext
                
                try:
                    with open(file_path, 'rb') as f:
                        tags = exifread.process_file(f)
                        
                        if not tags:
                            print(f"  警告: 无法从RAW文件中提取任何EXIF标签")
                        else:
                            # 记录标签数量
                            print(f"  成功提取到 {len(tags)} 个EXIF标签")
                            
                            # 检查是否有尺寸相关标签
                            has_size_info = any(tag in tags for tag in ['EXIF ExifImageWidth', 'EXIF ExifImageLength', 'Image Width', 'Image Length'])
                            if has_size_info:
                                print("  文件包含尺寸信息标签")
                                # 尝试提取尺寸信息
                                for tag in ['EXIF ExifImageWidth', 'EXIF ExifImageLength', 'Image Width', 'Image Length']:
                                    if tag in tags:
                                        try:
                                            tag_value = str(tags[tag])
                                            if 'Width' in tag:
                                                if 'x' in tag_value.lower():
                                                    metadata['width'] = int(tag_value.lower().split('x')[0].strip())
                                                else:
                                                    metadata['width'] = int(tag_value)
                                            elif 'Length' in tag:
                                                if 'x' in tag_value.lower():
                                                    metadata['height'] = int(tag_value.lower().split('x')[1].strip()) if len(tag_value.lower().split('x')) > 1 else int(tag_value)
                                                else:
                                                    metadata['height'] = int(tag_value)
                                        except (ValueError, TypeError):
                                            continue
                            else:
                                print("  文件不包含尺寸信息标签")
                            
                            # 保存标签（排除大尺寸的缩略图数据）
                            for tag in tags.keys():
                                if tag not in ['JPEGThumbnail', 'TIFFThumbnail', 'Filename', 'EXIF MakerNote']:
                                    try:
                                        # 对于大的值，截断显示
                                        tag_value = str(tags[tag])
                                        if len(tag_value) > 500:
                                            tag_value = tag_value[:500] + "... [截断显示]"
                                        metadata['exif'][tag] = tag_value
                                    except Exception as e:
                                        print(f"  保存标签 {tag} 失败: {e}")
                except Exception as e:
                    print(f"  读取RAW文件失败: {e}")
                    # 即使失败，我们已经添加了基本的文件格式信息
        
            # 保存元数据缓存
            try:
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"保存元数据缓存失败 {file_path}: {e}")
                
        except Exception as e:
            print(f"提取元数据失败 {file_path}: {e}")
            # 添加错误信息到元数据
            metadata['error'] = str(e)
        
        return metadata
    
    def fix_image_orientation(self, image: Image.Image) -> Image.Image:
        """根据EXIF方向信息校正图片方向"""
        try:
            # 获取EXIF数据
            exif = image._getexif()
            if exif:
                # 获取方向标签
                orientation = exif.get(0x0112, 1)  # EXIF方向标签
                
                # 根据方向信息旋转图片
                if orientation == 2:
                    image = image.transpose(Image.FLIP_LEFT_RIGHT)
                elif orientation == 3:
                    image = image.rotate(180)
                elif orientation == 4:
                    image = image.transpose(Image.FLIP_TOP_BOTTOM)
                elif orientation == 5:
                    image = image.rotate(-90).transpose(Image.FLIP_LEFT_RIGHT)
                elif orientation == 6:
                    image = image.rotate(-90)
                elif orientation == 7:
                    image = image.rotate(90).transpose(Image.FLIP_LEFT_RIGHT)
                elif orientation == 8:
                    image = image.rotate(90)
        except Exception as e:
            print(f"处理图片方向时出错: {e}")
        
        return image
    
    def clean_all_thumbnails(self):
        """清理所有图片目录下的缩略图缓存文件"""
        try:
            # 获取所有配置的图片目录
            image_dirs = self.config.config.get('image_directories', [])
            
            for image_dir in image_dirs:
                if not os.path.exists(image_dir):
                    continue
                
                # 遍历目录查找所有.album_cache文件夹
                for root, dirs, files in os.walk(image_dir):
                    if '.album_cache' in dirs:
                        cache_dir = os.path.join(root, '.album_cache')
                        
                        # 删除所有thumb_开头的缩略图文件
                        if os.path.exists(cache_dir):
                            for file in os.listdir(cache_dir):
                                if file.startswith('thumb_'):
                                    file_path = os.path.join(cache_dir, file)
                                    try:
                                        os.remove(file_path)
                                        print(f"已删除旧缩略图: {file_path}")
                                    except Exception as e:
                                        print(f"删除缩略图失败 {file_path}: {e}")
            
            print("所有旧缩略图缓存已清理完成")
        except Exception as e:
            print(f"清理缓存时发生错误: {e}")
    
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
            # 使用win32com.client来获取Windows文件星级评分
            from win32com.client import Dispatch
            import os
            import re
            
            # 创建Shell对象用于访问文件属性
            shell = Dispatch("Shell.Application")
            
            # 获取文件所在目录的Folder对象
            folder_path = os.path.dirname(file_path)
            file_name = os.path.basename(file_path)
            
            folder = shell.NameSpace(folder_path)
            if folder is None:
                print(f"无法访问目录: {folder_path}")
                return 0
            
            # 查找文件项
            item = None
            for i in range(0, folder.Items().Count):
                current_item = folder.Items().Item(i)
                if current_item.Name == file_name:
                    item = current_item
                    break
            
            if item is None:
                print(f"找不到文件: {file_name}")
                return 0
            
            # 获取星级评分 (索引19)
            rating_text = folder.GetDetailsOf(item, 19)
            
            # 解析"X 星级"格式的评分
            if rating_text and "星级" in rating_text:
                # 提取数字部分
                match = re.search(r'(\d+)', rating_text)
                if match:
                    star_count = int(match.group(1))
                    return star_count
            
            # 如果索引19失败，尝试其他常见索引
            rating_indexes = [18, 27, 165, 166]
            for idx in rating_indexes:
                if idx != 19:  # 已经检查过索引19了
                    rating_text = folder.GetDetailsOf(item, idx)
                    if rating_text and ('★' in rating_text or rating_text.isdigit()):
                        if '★' in rating_text:
                            star_count = rating_text.count('★')
                            return star_count
                        elif rating_text.isdigit():
                            return int(rating_text)
            
            return 0
        except Exception as e:
            print(f"获取星级评分时出错: {e}")
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
         
    def find_preview_image_in_subdirectories(self, directory: str) -> Optional[Dict]:
        """在子目录中查找预览图片"""
        try:
            # 遍历目录下的所有子目录
            for item in os.listdir(directory):
                if item.startswith('.'):  # 跳过隐藏目录
                    continue
                        
                item_path = os.path.join(directory, item)
                
                if os.path.isdir(item_path):
                    # 先检查子目录是否有图片
                    try:
                        for sub_item in os.listdir(item_path):
                            if sub_item.startswith('.'):
                                continue
                            
                            sub_item_path = os.path.join(item_path, sub_item)
                            if os.path.isfile(sub_item_path) and self.is_supported_format(sub_item_path):
                                metadata = self.extract_metadata(sub_item_path)
                                image_info = {
                                    'file_path': sub_item_path,
                                    'relative_path': os.path.relpath(sub_item_path, directory),
                                    'thumbnail_path': self.generate_thumbnail(sub_item_path),
                                    'preview_path': self.generate_preview(sub_item_path),
                                    'metadata': metadata
                                }
                                return image_info
                    except Exception as e:
                        print(f"检查子目录 {item_path} 时出错: {str(e)}")
                    
                    # 如果子目录中没有图片，递归查找更深层次的子目录
                    preview_image = self.find_preview_image_in_subdirectories(item_path)
                    if preview_image:
                        return preview_image
        except Exception as e:
            print(f"在子目录中查找预览图时出错: {str(e)}")
        
        return None
         
    def get_directory_preview(self, directory: str) -> Optional[Dict]:
        """获取目录的预览图片信息"""
        # 先尝试在当前目录查找
        current_images = self.scan_current_directory(directory)
        if current_images:
            return current_images[0]
            
        # 如果当前目录没有图片，递归查找子目录
        return self.find_preview_image_in_subdirectories(directory)
