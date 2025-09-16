#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试image_processor.py中的extract_metadata方法是否正确包含星级评分
"""
import os
import sys

# 将当前目录添加到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入所需的类
from image_processor import ImageProcessor
from config import Config

if __name__ == "__main__":
    # 测试文件路径
    test_file_path = r"E:\测试目录\1\653A7189.jpg"
    
    print(f"===== 测试元数据提取功能 =====")
    print(f"测试文件: {test_file_path}")
    print(f"文件是否存在: {os.path.exists(test_file_path)}")
    
    # 创建Config实例，然后用它初始化ImageProcessor
    print("\n创建Config实例...")
    config = Config()
    
    print("创建ImageProcessor实例...")
    processor = ImageProcessor(config)
    
    # 调用extract_metadata方法
    print("\n调用extract_metadata方法...")
    metadata = processor.extract_metadata(test_file_path)
    
    # 打印完整的元数据
    print(f"\n完整元数据: ")
    for key, value in metadata.items():
        print(f"  {key}: {value}")
    
    # 特别关注rating字段
    print(f"\n元数据中的星级评分: {metadata.get('rating', 'Not found')}星")
    print(f"预期星级评分: 2星")
    print(f"测试结果: {'通过' if metadata.get('rating') == 2 else '失败'}")
    print("====================================")