import os
import sys
import json
import shutil

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入必要的模块
from config import Config
from image_processor import ImageProcessor, WIN32_AVAILABLE
from datetime import datetime

class ImageRatingIntegrationTester:
    """图片星级评分系统集成测试器"""
    
    def __init__(self):
        """初始化测试器"""
        # 正确初始化Config和ImageProcessor
        self.config = Config()
        self.processor = ImageProcessor(self.config)
        
        # 设置测试参数
        self.test_image_path = r"E:\测试目录\1\653A7189.jpg"  # 使用原始字符串前缀处理Windows路径
        self.temp_test_image = "temp_test_image.jpg"  # 临时测试图片
        self.test_rating = 3  # 测试星级评分
        self.original_rating = 0  # 原始星级评分
        
        print("===== 图片星级评分系统集成测试 =====")
        print(f"Windows支持状态: {WIN32_AVAILABLE}")
        print(f"测试图片路径: {self.test_image_path}")
        print(f"测试星级评分: {self.test_rating}")
        print("=" * 50)
    
    def prepare_test(self):
        """准备测试环境"""
        print("准备测试环境...")
        
        # 检查测试图片是否存在
        if not os.path.exists(self.test_image_path):
            print(f"错误: 测试图片不存在 - {self.test_image_path}")
            print("请提供有效的测试图片路径")
            return False
        
        # 创建临时测试图片副本
        try:
            shutil.copy2(self.test_image_path, self.temp_test_image)
            print(f"已创建临时测试图片: {self.temp_test_image}")
        except Exception as e:
            print(f"创建临时测试图片失败: {e}")
            return False
        
        # 记录原始星级评分
        self.original_rating = self.processor.get_windows_rating(self.temp_test_image)
        print(f"原始星级评分: {self.original_rating}")
        
        return True
    
    def run_test(self):
        """运行测试"""
        if not self.prepare_test():
            return False
        
        try:
            print("\n开始测试...")
            
            # 1. 测试设置星级评分
            print(f"\n1. 测试设置星级评分 ({self.test_rating}星)...")
            result = self.processor.set_windows_rating(self.temp_test_image, self.test_rating)
            print(f"设置星级结果: {'成功' if result else '失败'}")
            
            # 2. 测试获取星级评分
            print("\n2. 测试获取星级评分...")
            current_rating = self.processor.get_windows_rating(self.temp_test_image)
            print(f"获取到的星级评分: {current_rating}")
            print(f"评分匹配测试: {'通过' if current_rating == self.test_rating else '失败'}")
            
            # 3. 检查元数据缓存文件
            print("\n3. 检查元数据缓存文件...")
            cache_dir = self.processor.get_cache_dir(self.temp_test_image)
            file_hash = self.processor.get_file_hash(self.temp_test_image)
            metadata_path = os.path.join(cache_dir, f"meta_{file_hash}.json")
            
            if os.path.exists(metadata_path):
                print(f"找到元数据缓存文件: {metadata_path}")
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                if 'rating' in metadata:
                    cache_rating = metadata['rating']
                    print(f"缓存中的星级评分: {cache_rating}")
                    print(f"缓存评分匹配测试: {'通过' if cache_rating == self.test_rating else '失败'}")
                else:
                    print("错误: 缓存文件中没有rating字段")
            else:
                print(f"错误: 元数据缓存文件不存在 - {metadata_path}")
            
            # 4. 测试移除星级评分
            print("\n4. 测试移除星级评分 (设置为0星)...")
            result = self.processor.set_windows_rating(self.temp_test_image, 0)
            print(f"移除星级结果: {'成功' if result else '失败'}")
            
            current_rating = self.processor.get_windows_rating(self.temp_test_image)
            print(f"移除后获取到的星级评分: {current_rating}")
            print(f"移除评分测试: {'通过' if current_rating == 0 else '失败'}")
            
            # 5. 恢复原始星级评分
            print("\n5. 恢复原始星级评分...")
            result = self.processor.set_windows_rating(self.temp_test_image, self.original_rating)
            print(f"恢复星级结果: {'成功' if result else '失败'}")
            
            return True
        except Exception as e:
            print(f"测试过程中出错: {e}")
            return False
        finally:
            self.cleanup_test()
    
    def cleanup_test(self):
        """清理测试环境"""
        print("\n清理测试环境...")
        
        # 删除临时测试图片
        if os.path.exists(self.temp_test_image):
            try:
                os.remove(self.temp_test_image)
                print(f"已删除临时测试图片: {self.temp_test_image}")
            except Exception as e:
                print(f"删除临时测试图片失败: {e}")
        
        print("\n===== 测试完成 =====")

if __name__ == "__main__":
    tester = ImageRatingIntegrationTester()
    tester.run_test()