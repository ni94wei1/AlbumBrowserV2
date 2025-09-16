#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试image_processor.py中修复的Windows文件星级评分读取功能
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
    
    print(f"===== 测试Windows文件星级评分读取功能 =====")
    print(f"测试文件: {test_file_path}")
    print(f"文件是否存在: {os.path.exists(test_file_path)}")
    
    # 创建Config实例，然后用它初始化ImageProcessor
    print("\n创建Config实例...")
    config = Config()
    
    print("创建ImageProcessor实例...")
    processor = ImageProcessor(config)
    
    # 调用修复后的get_windows_rating方法
    print("\n调用image_processor.py中的get_windows_rating方法...")
    rating = processor.get_windows_rating(test_file_path)
    
    print(f"\n获取到的星级评分: {rating}星")
    print(f"预期星级评分: 2星")
    print(f"测试结果: {'通过' if rating == 2 else '失败'}")
    print("====================================")