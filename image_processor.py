import os
import json
import hashlib
import shutil
import os
import tempfile
import threading
import queue
import subprocess
from pathlib import Path
from PIL import Image, ExifTags, ImageDraw, ImageFont
from PIL.ExifTags import TAGS
import exifread
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from PIL import ImageOps

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

# 使用exiftool实现的星级评分函数
def get_rating(file_path: str) -> int:
    """使用exiftool获取图片的星级评分"""
    try:
        result = subprocess.run(
            ["exiftool", "-Rating", "-s3", str(file_path)],
            capture_output=True, text=True, encoding="mbcs", errors="ignore"
        )
        if result.returncode != 0:
            print(f"读取评级失败: {result.stderr.strip()}")
            return 0
        rating_str = result.stdout.strip()
        return int(rating_str) if rating_str.isdigit() else 0
    except Exception as e:
        print(f"获取星级评分出错: {e}")
        return 0

def set_rating(file_path: str, stars: int) -> bool:
    """使用exiftool设置图片的星级评分"""
    try:
        if stars < 0 or stars > 5:
            print(f"错误: 无效的星级评分 (必须是0-5之间的整数) - {stars}")
            return False
        
        if not os.path.exists(file_path):
            print(f"错误: 文件不存在 - {file_path}")
            return False
        
        result = subprocess.run(
            ["exiftool", f"-Rating={stars}", "-overwrite_original", str(file_path)],
            capture_output=True, text=True, encoding="mbcs", errors="ignore"
        )
        if result.returncode != 0:
            print(f"写入评级失败: {result.stderr.strip()}")
            return False
        
        print(f"成功设置评分: {stars}星 到文件: {file_path}")
        return True
    except Exception as e:
        print(f"设置评分失败: {e}")
        return False

class ImageProcessor:
    def __init__(self, config):
        self.config = config
        # 不再使用统一的cache目录，改为在图片原目录下生成隐藏文件夹
        
        # 异步缓存生成相关设置
        self.cache_queue = queue.Queue()  # 缓存生成队列
        self.priority_queue = queue.PriorityQueue()  # 优先级队列，用于处理用户请求的图片
        self.cache_workers = []  # 工作线程列表
        self.max_workers = 2  # 最大工作线程数
        self.running = True  # 工作线程运行状态
        
        # 启动工作线程
        self._start_workers()
        
        # 记录需要优先处理的图片
        self.priority_images = set()
        
        # 注册退出时的清理函数
        import atexit
        atexit.register(self._stop_workers)
    
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
    
    def _start_workers(self):
        """启动工作线程"""
        for _ in range(self.max_workers):
            worker = threading.Thread(target=self._worker_thread, daemon=True)
            worker.start()
            self.cache_workers.append(worker)
        print(f"已启动 {self.max_workers} 个缓存生成工作线程")
    
    def _stop_workers(self):
        """停止工作线程"""
        self.running = False
        # 清空队列并添加结束信号
        for _ in range(self.max_workers):
            self.cache_queue.put(None)
            self.priority_queue.put((0, None))
        # 等待所有线程结束
        for worker in self.cache_workers:
            worker.join(timeout=2.0)
        print(f"已停止所有缓存生成工作线程")
    
    def _worker_thread(self):
        """工作线程主函数，处理异步生成缩略图和预览图的任务"""
        while self.running:
            try:
                # 先检查优先级队列（优先处理用户直接点击查看的图片）
                try:
                    # 使用较短的超时，以便定期检查running状态
                    priority, task = self.priority_queue.get(timeout=0.5)
                    if task is None:  # 结束信号
                        self.priority_queue.task_done()
                        break
                    # 处理优先级任务
                    if task['type'] == 'preview':
                        file_path = task['file_path']
                        print(f"优先级处理预览图: {file_path}")
                        self._process_preview_task(file_path)
                    self.priority_queue.task_done()
                    continue  # 处理完优先级任务后，继续下一次循环，优先处理其他优先级任务
                except queue.Empty:
                    pass  # 优先级队列为空，检查普通队列
                
                # 检查普通队列（处理目录浏览时的批量生成任务）
                try:
                    task = self.cache_queue.get(timeout=0.5)
                    if task is None:  # 结束信号
                        self.cache_queue.task_done()
                        break
                    # 处理普通任务
                    file_path = task['file_path']
                    task_type = task['type']
                    
                    # 检查这个任务是否已被添加到优先级队列
                    with threading.Lock():
                        if task_type == 'preview' and file_path in self.priority_images:
                            # 如果已经在优先级队列中，跳过此任务
                            self.cache_queue.task_done()
                            continue
                    
                    # 根据任务类型处理
                    if task_type == 'thumbnail':
                        print(f"异步生成缩略图: {file_path}")
                        self.generate_thumbnail(file_path)
                    elif task_type == 'preview':
                        print(f"异步生成预览图: {file_path}")
                        self.generate_preview(file_path)
                    elif task_type == 'metadata':
                        print(f"异步提取元数据: {file_path}")
                        self.extract_metadata(file_path)
                    
                    self.cache_queue.task_done()
                except queue.Empty:
                    pass  # 两个队列都为空，继续循环
            except Exception as e:
                print(f"工作线程异常: {e}")
    
    def _process_preview_task(self, file_path):
        """处理预览图任务"""
        try:
            # 先检查是否已经生成了预览图
            cache_dir = self.get_cache_dir(file_path)
            file_hash = self.get_file_hash(file_path)
            preview_path = os.path.join(cache_dir, f"preview_{file_hash}.jpg")
            
            if not os.path.exists(preview_path):
                print(f"优先级处理预览图: {file_path}")
                self.generate_preview(file_path)
            else:
                print(f"预览图已存在，无需重新生成: {file_path}")
            
            # 从优先级图片集合中移除
            with threading.Lock():
                self.priority_images.discard(file_path)
        except Exception as e:
            print(f"处理预览图任务失败 {file_path}: {e}")
    
    def prioritize_preview(self, file_path):
        """优先处理指定文件的预览图生成
        
        当用户点击查看大图但预览图尚未生成时，调用此方法将预览图生成任务优先处理
        
        Args:
            file_path: 需要优先处理的图片文件路径
        
        Returns:
            bool: 是否成功添加到优先级队列
        """
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                print(f"错误: 文件不存在 - {file_path}")
                return False
            
            # 检查预览图是否已存在
            cache_dir = self.get_cache_dir(file_path)
            file_hash = self.get_file_hash(file_path)
            preview_path = os.path.join(cache_dir, f"preview_{file_hash}.jpg")
            
            if os.path.exists(preview_path):
                print(f"预览图已存在，无需优先处理: {file_path}")
                return True
            
            # 检查是否已经在优先级队列中
            with threading.Lock():
                if file_path in self.priority_images:
                    print(f"预览图已在优先级队列中: {file_path}")
                    return True
                
                # 添加到优先级集合和队列
                self.priority_images.add(file_path)
                # 使用高优先级（较小的数字表示较高优先级）
                self.priority_queue.put((1, {'type': 'preview', 'file_path': file_path}))
                
            print(f"已将{file_path}添加到预览图优先级队列")
            return True
        except Exception as e:
            print(f"添加预览图优先级任务失败: {e}")
            # 出现异常时，从优先级集合中移除（如果已添加）
            with threading.Lock():
                self.priority_images.discard(file_path)
            return False
    
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
        """统一处理RAW文件预览图：提取嵌入JPEG或占位图，并正确修正方向"""
        try:
            file_extension = os.path.splitext(file_path)[1].lower()
            print(f"处理RAW文件: {file_path} 扩展名: {file_extension}")
            temp_image_path = None
            try:
                if file_extension == '.cr3':
                    with open(file_path, 'rb') as f:
                        file_data = f.read()
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
                                cand = file_data[jpeg_start:jpeg_end+2]
                                if len(cand) > best_jpeg_size:
                                    best_jpeg_size = len(cand)
                                    best_jpeg_data = cand
                        if best_jpeg_data:
                            temp_image_path = os.path.join(cache_dir, f"temp_thumb_preview_{file_hash}.jpg")
                            with open(temp_image_path, 'wb') as jf:
                                jf.write(best_jpeg_data)
                            print(f"  成功提取CR3嵌入JPEG预览图")
            except Exception as e:
                print(f"  提取缩略图时出错: {e}")
            if not temp_image_path:
                placeholder_size = 300
                placeholder = Image.new('RGB', (placeholder_size, placeholder_size), color='gray')
                draw = ImageDraw.Draw(placeholder)
                text = "RAW\n文件"
                font = ImageFont.load_default()
                tb = draw.textbbox((0, 0), text, font=font)
                position = ((placeholder_size - (tb[2]-tb[0]))//2, (placeholder_size - (tb[3]-tb[1]))//2)
                draw.text(position, text, fill='white', font=font)
                temp_image_path = os.path.join(cache_dir, f"temp_thumb_preview_{file_hash}.jpg")
                placeholder.save(temp_image_path, 'JPEG', quality=85)
            if temp_image_path and os.path.exists(temp_image_path):
                image = Image.open(temp_image_path)
                image = self.fix_image_orientation(image)
                try:
                    os.remove(temp_image_path)
                except:
                    pass
                return image
            else:
                print("  未能创建临时图像文件")
                return None
        except Exception as e:
            print(f"处理RAW文件时发生错误: {e}")
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
                        # image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        target_size = (new_width, new_height) if width and height else (width or new_width, height or new_height)
                        image = ImageOps.fit(image, target_size, Image.Resampling.LANCZOS, centering=(0.5, 0.5))

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
        """生成预览图：按EXIF修正方向并缩放"""
        cache_dir = self.get_cache_dir(file_path)
        file_hash = self.get_file_hash(file_path)
        preview_path = os.path.join(cache_dir, f"preview_{file_hash}.jpg")
        if os.path.exists(preview_path):
            return preview_path
        try:
            if self.is_raw_format(file_path):
                image = self._process_raw_file_for_preview(file_path, file_hash, cache_dir)
                if not image:
                    return None
                max_size = self.config.config.get('preview_max_size', 1600)
                preview_quality = self.config.config.get('preview_quality', 75)
                if self._resize_and_save_image(image, preview_path, max_size, 0, preview_quality):
                    return preview_path
                return None
            image = self.load_image(file_path)
            if not image:
                return None
            image = self.fix_image_orientation(image)
            max_size = self.config.config.get('preview_max_size', 1600)
            preview_quality = self.config.config.get('preview_quality', 75)
            if self._resize_and_save_image(image, preview_path, max_size, 0, preview_quality):
                return preview_path
            return None
        except Exception as e:
            print(f"生成预览图失败 {file_path}: {e}")
            return None
    
    def extract_metadata(self, file_path: str) -> Dict:
        """提取图片元数据"""
        cache_dir = self.get_cache_dir(file_path)
        file_hash = self.get_file_hash(file_path)
        metadata_path = os.path.join(cache_dir, f"meta_{file_hash}.json")
        
        # 强制打印调试信息到stderr，确保能被看到
        import sys
        print("\n========== extract_metadata 被调用 ==========", file=sys.stderr)
        print(f"文件路径: {file_path}", file=sys.stderr)
        print(f"缓存文件路径: {metadata_path}", file=sys.stderr)
        print(f"缓存文件存在: {os.path.exists(metadata_path)}", file=sys.stderr)
        
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    cached_metadata = json.load(f)
                    print(f"从缓存读取到的rating: {cached_metadata.get('rating', 'Not found')}", file=sys.stderr)
                    return cached_metadata
            except Exception as e:
                print(f"加载缓存的元数据失败 {file_path}: {e}", file=sys.stderr)
        
        # 打印WIN32_AVAILABLE状态
        print(f"WIN32_AVAILABLE: {WIN32_AVAILABLE}", file=sys.stderr)
        
        # 直接测试get_windows_rating方法
        print("调用get_windows_rating...", file=sys.stderr)
        rating_value = self.get_windows_rating(file_path)
        print(f"get_windows_rating返回值: {rating_value}", file=sys.stderr)
        
        metadata = {
            'filename': os.path.basename(file_path),
            'file_size': os.path.getsize(file_path),
            'modified_time': os.path.getmtime(file_path),
            'rating': rating_value,
            'exif': {},
            'is_raw': self.is_raw_format(file_path)
        }
        
        print(f"构造的metadata中的rating: {metadata['rating']}", file=sys.stderr)
        print("===========================================", file=sys.stderr)
        
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
        """根据EXIF自动修正图片方向（使用Pillow的exif_transpose，推荐方法）"""
        try:
            from PIL import ImageOps
            image = ImageOps.exif_transpose(image)
        except Exception as e:
            print(f"处理图片方向时出错 (exif_transpose): {e}")
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
        """获取图片星级评分
        
        使用exiftool直接从图片文件中读取星级评分
        """
        try:
            if not os.path.exists(file_path):
                print(f"错误: 文件不存在 - {file_path}")
                return 0
            
            # 直接使用exiftool获取评分
            rating_value = get_rating(file_path)
            print(f"从文件获取评分: {rating_value} 对于文件: {file_path}")
            return rating_value
        except Exception as e:
            print(f"获取星级评分时出错: {e}")
            return 0
    
    def set_windows_rating(self, file_path: str, rating: int) -> bool:
        """设置图片星级评分
        
        使用exiftool直接将星级评分写入图片文件
        并同步更新缓存目录中的meta_xx.json文件
        """
        try:
            # 验证参数
            if not isinstance(rating, int) or rating < 0 or rating > 5:
                print(f"错误: 无效的星级评分 (必须是0-5之间的整数) - {rating}")
                return False
            
            if not os.path.exists(file_path):
                print(f"错误: 文件不存在 - {file_path}")
                return False
            
            # 使用exiftool设置评分到原图
            rating_set = set_rating(file_path, rating)
            
            # 更新元数据缓存
            if rating_set:
                try:
                    cache_dir = self.get_cache_dir(file_path)
                    file_hash = self.get_file_hash(file_path)
                    metadata_path = os.path.join(cache_dir, f"meta_{file_hash}.json")
                    
                    if os.path.exists(metadata_path):
                        with open(metadata_path, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        metadata['rating'] = rating
                        with open(metadata_path, 'w', encoding='utf-8') as f:
                            json.dump(metadata, f, indent=2, ensure_ascii=False)
                        print(f"成功更新元数据缓存: {metadata_path}")
                except Exception as e:
                    print(f"更新元数据缓存失败: {e}")
                    # 即使缓存更新失败，评分设置仍然成功
            
            return rating_set
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
        """扫描当前目录中的图片文件（不递归子目录）
        
        优化逻辑：
        1. 先扫描所有图片文件，收集基本信息（不等待元数据提取完成）
        2. 只进行必要的文件检查和基本信息收集
        3. 所有缩略图和预览图全部异步生成，不阻塞主流程
        4. 返回不完整的图片信息，客户端后续可以异步加载
        """
        images = []
        image_paths = []
        
        try:
            # 快速扫描阶段：只收集基本文件信息，不做耗时操作
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
                        # 生成缓存路径，但不立即生成缓存或提取元数据
                        cache_dir = self.get_cache_dir(display_path)
                        file_hash = self.get_file_hash(display_path)
                        thumbnail_path = os.path.join(cache_dir, f"thumb_{file_hash}.jpg")
                        preview_path = os.path.join(cache_dir, f"preview_{file_hash}.jpg")
                        metadata_path = os.path.join(cache_dir, f"meta_{file_hash}.json")
                        
                        # 构建基本图片信息
                        # 注意：这里不调用extract_metadata，只提供基本信息
                        is_raw = self.is_raw_format(display_path)
                        
                        # 只获取文件名、文件大小和修改时间等基本信息
                        basic_info = {
                            'filename': os.path.basename(display_path),
                            'file_size': os.path.getsize(display_path),
                            'modified_time': os.path.getmtime(display_path),
                            'rating': 0,  # 默认评分
                            'exif': {},
                            'is_raw': is_raw
                        }
                        
                        # 如果元数据缓存已存在，快速加载
                        cached_metadata = None
                        if os.path.exists(metadata_path):
                            try:
                                with open(metadata_path, 'r', encoding='utf-8') as f:
                                    cached_metadata = json.load(f)
                            except Exception as e:
                                print(f"加载缓存的元数据失败 {display_path}: {e}")
                        
                        image_info = {
                            'file_path': display_path,
                            'relative_path': os.path.relpath(display_path, directory),
                            'thumbnail_path': thumbnail_path if os.path.exists(thumbnail_path) else None,
                            'preview_path': preview_path if os.path.exists(preview_path) else None,
                            'metadata': cached_metadata or basic_info,
                            'has_raw': raw_path is not None,
                            'has_jpg': jpg_path is not None,
                            'thumbnail_exists': os.path.exists(thumbnail_path),
                            'preview_exists': os.path.exists(preview_path),
                            'metadata_exists': cached_metadata is not None
                        }
                        
                        images.append(image_info)
                        image_paths.append(display_path)
            
            # 异步处理阶段：将所有图片的处理任务加入队列，不阻塞返回
            # 1. 首先添加所有元数据提取任务
            for image_path in image_paths:
                self.cache_queue.put({'type': 'metadata', 'file_path': image_path})
            
            # 2. 然后添加所有缩略图生成任务
            for image_path in image_paths:
                self.cache_queue.put({'type': 'thumbnail', 'file_path': image_path})
            
            # 3. 最后添加所有预览图生成任务
            for image_path in image_paths:
                self.cache_queue.put({'type': 'preview', 'file_path': image_path})
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
