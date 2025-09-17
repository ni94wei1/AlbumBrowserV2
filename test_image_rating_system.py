import os
import json
import time
from datetime import datetime

"""
测试图片星级评分系统的替代方案

此脚本将：
1. 创建一个统一的评分数据库文件来存储所有图片的评分
2. 实现评分的读取、设置、删除功能
3. 与现有缓存系统集成
4. 提供测试用例验证功能正确性
"""

class ImageRatingSystem:
    """\图片星级评分管理系统"""
    
    def __init__(self, db_path="ratings_db.json"):
        """
        初始化评分系统
        
        参数:
            db_path: 评分数据库文件路径
        """
        self.db_path = db_path
        self.ratings_db = {}
        self._load_database()
    
    def _load_database(self):
        """从文件加载评分数据库"""
        try:
            if os.path.exists(self.db_path):
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    self.ratings_db = json.load(f)
                print(f"成功加载评分数据库，共包含 {len(self.ratings_db)} 条评分记录")
            else:
                print(f"评分数据库文件不存在，将创建新文件: {self.db_path}")
                self._save_database()
        except Exception as e:
            print(f"加载评分数据库失败: {e}")
            self.ratings_db = {}
    
    def _save_database(self):
        """保存评分数据库到文件"""
        try:
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(self.ratings_db, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存评分数据库失败: {e}")
    
    def _get_file_key(self, file_path):
        """
        获取文件的唯一标识键
        
        参数:
            file_path: 文件路径
        
        返回:
            str: 文件的唯一标识键
        """
        # 使用绝对路径作为键，确保唯一性
        return os.path.abspath(file_path)
    
    def get_rating(self, file_path):
        """
        获取图片的星级评分
        
        参数:
            file_path: 图片文件路径
        
        返回:
            int: 星级评分 (0-5)
        """
        file_key = self._get_file_key(file_path)
        if file_key in self.ratings_db:
            rating_info = self.ratings_db[file_key]
            return rating_info.get('rating', 0)
        return 0
    
    def set_rating(self, file_path, rating):
        """
        设置图片的星级评分
        
        参数:
            file_path: 图片文件路径
            rating: 星级评分 (0-5)
        
        返回:
            bool: 是否设置成功
        """
        # 验证参数
        if not isinstance(rating, int) or rating < 0 or rating > 5:
            print(f"错误: 无效的星级评分 (必须是0-5之间的整数) - {rating}")
            return False
        
        if not os.path.exists(file_path):
            print(f"错误: 文件不存在 - {file_path}")
            return False
        
        try:
            file_key = self._get_file_key(file_path)
            timestamp = datetime.now().isoformat()
            
            # 存储评分信息，包括评分值、时间戳和文件基本信息
            self.ratings_db[file_key] = {
                'rating': rating,
                'timestamp': timestamp,
                'filename': os.path.basename(file_path),
                'directory': os.path.dirname(file_path)
            }
            
            # 保存数据库
            self._save_database()
            
            # 同时尝试更新缓存文件（如果存在）
            self._update_cache_file(file_path, rating)
            
            print(f"成功设置评分: {rating}星 到文件: {file_path}")
            return True
        except Exception as e:
            print(f"设置评分失败: {e}")
            return False
    
    def _update_cache_file(self, file_path, rating):
        """
        更新图片的缓存元数据文件
        
        参数:
            file_path: 图片文件路径
            rating: 星级评分
        """
        try:
            # 尝试按照现有系统的逻辑找到缓存文件
            # 这里需要根据实际的缓存文件路径规则来实现
            # 以下是一个示例实现
            
            # 从file_path中提取目录信息
            file_dir = os.path.dirname(file_path)
            cache_dir = os.path.join(file_dir, '.album_cache')
            
            if not os.path.exists(cache_dir):
                # 缓存目录不存在，创建它
                os.makedirs(cache_dir)
            
            # 尝试找到对应的元数据缓存文件
            # 注意：这里的命名规则需要与实际系统一致
            file_name = os.path.basename(file_path)
            file_base = os.path.splitext(file_name)[0]
            
            # 查找可能的元数据文件
            for file in os.listdir(cache_dir):
                if file.startswith('meta_') and file.endswith('.json'):
                    meta_path = os.path.join(cache_dir, file)
                    try:
                        with open(meta_path, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                        
                        # 检查这个元数据文件是否对应目标文件
                        if metadata.get('filename') == file_name or \
                           metadata.get('original_path') == file_path or \
                           os.path.basename(metadata.get('file_path', '')) == file_name:
                            # 更新评分
                            metadata['rating'] = rating
                            with open(meta_path, 'w', encoding='utf-8') as f:
                                json.dump(metadata, f, indent=2, ensure_ascii=False)
                            print(f"成功更新缓存文件: {meta_path}")
                            break
                    except Exception as e:
                        print(f"读取缓存文件失败 {meta_path}: {e}")
        except Exception as e:
            print(f"更新缓存文件时发生错误: {e}")
            # 这里不抛出异常，因为即使缓存更新失败，评分设置仍然成功
    
    def get_all_ratings(self):
        """
        获取所有评分记录
        
        返回:
            dict: 所有评分记录
        """
        return self.ratings_db
    
    def remove_rating(self, file_path):
        """
        移除图片的星级评分
        
        参数:
            file_path: 图片文件路径
        
        返回:
            bool: 是否移除成功
        """
        try:
            file_key = self._get_file_key(file_path)
            if file_key in self.ratings_db:
                del self.ratings_db[file_key]
                self._save_database()
                print(f"成功移除文件的评分: {file_path}")
                return True
            return False
        except Exception as e:
            print(f"移除评分失败: {e}")
            return False

# 测试函数
def run_tests():
    print("===== 图片星级评分系统测试 =====")
    
    # 创建测试文件
    test_file = "test_image.jpg"
    try:
        # 创建一个空的测试文件
        with open(test_file, 'w') as f:
            f.write("test image content")
        print(f"创建测试文件: {test_file}")
        
        # 初始化评分系统
        rating_system = ImageRatingSystem("test_ratings_db.json")
        
        # 测试获取不存在的评分
        initial_rating = rating_system.get_rating(test_file)
        print(f"初始评分: {initial_rating}星")
        
        # 测试设置评分
        test_ratings = [3, 5, 0, 2]
        for rating in test_ratings:
            print(f"\n设置评分: {rating}星")
            success = rating_system.set_rating(test_file, rating)
            if success:
                # 验证设置结果
                new_rating = rating_system.get_rating(test_file)
                print(f"验证结果: 实际评分 {new_rating}星")
                
                if new_rating == rating:
                    print("✓ 验证成功")
                else:
                    print("✗ 验证失败")
            else:
                print("✗ 设置失败")
        
        # 测试移除评分
        print(f"\n移除评分")
        success = rating_system.remove_rating(test_file)
        if success:
            # 验证移除结果
            new_rating = rating_system.get_rating(test_file)
            print(f"移除后评分: {new_rating}星")
            
            if new_rating == 0:
                print("✓ 验证成功")
            else:
                print("✗ 验证失败")
        else:
            print("✗ 移除失败")
        
        # 显示所有评分记录
        print(f"\n所有评分记录: {len(rating_system.get_all_ratings())}")
        
    finally:
        # 清理测试文件
        if os.path.exists(test_file):
            os.remove(test_file)
            print(f"删除测试文件: {test_file}")
        
        # 可选：删除测试数据库文件
        # if os.path.exists("test_ratings_db.json"):
        #     os.remove("test_ratings_db.json")
        #     print("删除测试数据库文件")
    
    print("\n===== 测试完成 =====")

if __name__ == "__main__":
    run_tests()