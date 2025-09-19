import sys
import os
from image_processor import get_rating, set_rating, ImageProcessor
import json

# 确保中文显示正常
sys.stdout.reconfigure(encoding='utf-8')

def test_rating_functions(file_path):
    """测试星级读取和写入功能"""
    print(f"\n=== 测试文件: {file_path} ===")
    
    # 1. 初始评分检查
    initial_rating = get_rating(file_path)
    print(f"初始评分: {initial_rating}⭐")
    
    # 2. 设置新评分
    new_rating = 3 if initial_rating != 3 else 4  # 避免设置相同的评分
    success = set_rating(file_path, new_rating)
    print(f"设置评分到 {new_rating}⭐: {'成功' if success else '失败'}")
    
    # 3. 验证评分是否设置成功
    if success:
        updated_rating = get_rating(file_path)
        print(f"更新后评分: {updated_rating}⭐")
        
        # 4. 检查缓存文件是否更新
        processor = ImageProcessor({"config": {}})
        cache_dir = processor.get_cache_dir(file_path)
        file_hash = processor.get_file_hash(file_path)
        metadata_path = os.path.join(cache_dir, f"meta_{file_hash}.json")
        
        print(f"缓存文件路径: {metadata_path}")
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            cache_rating = metadata.get('rating', 0)
            print(f"缓存文件中的评分: {cache_rating}⭐")
            
            # 验证缓存文件中的评分是否与实际评分一致
            if cache_rating == updated_rating:
                print("✓ 缓存文件评分与实际评分一致")
            else:
                print("✗ 缓存文件评分与实际评分不一致")
        else:
            print("缓存文件不存在，尝试提取元数据...")
            # 尝试提取元数据来创建缓存文件
            metadata = processor.extract_metadata(file_path)
            print(f"提取的元数据评分: {metadata.get('rating', 0)}⭐")
    
    # 5. 恢复原始评分
    if success:
        restore_success = set_rating(file_path, initial_rating)
        print(f"恢复原始评分 {initial_rating}⭐: {'成功' if restore_success else '失败'}")
        
if __name__ == "__main__":
    # 如果提供了命令行参数，使用提供的文件路径
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
    else:
        # 否则使用默认测试文件
        test_file = r"E:\测试目录\1\653A7189.jpg"
        print(f"未提供文件路径，使用默认测试文件: {test_file}")
        print("使用方法: python test_exiftool_rating.py <图片文件路径>")
    
    if os.path.exists(test_file):
        test_rating_functions(test_file)
    else:
        print(f"错误: 文件不存在 - {test_file}")
        sys.exit(1)