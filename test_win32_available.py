#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试WIN32_AVAILABLE变量和get_windows_rating方法的执行情况
"""
import os
import sys

# 将当前目录添加到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 直接导入image_processor模块
try:
    import image_processor
    print("成功导入image_processor模块")
    
    # 打印WIN32_AVAILABLE变量的值
    print(f"WIN32_AVAILABLE变量的值: {image_processor.WIN32_AVAILABLE}")
    
    # 测试win32com.client模块是否可用
    try:
        from win32com.client import Dispatch
        print("win32com.client模块可用")
        
        # 尝试创建Shell对象
        try:
            shell = Dispatch("Shell.Application")
            print("成功创建Shell.Application对象")
        except Exception as e:
            print(f"创建Shell对象失败: {e}")
    except ImportError as e:
        print(f"导入win32com.client失败: {e}")
    
    # 尝试导入win32file和win32con
    try:
        import win32file
        import win32con
        print("win32file和win32con模块可用")
    except ImportError as e:
        print(f"导入win32file或win32con失败: {e}")
        
    # 创建ImageProcessor实例并测试get_windows_rating方法
    from config import Config
    from image_processor import ImageProcessor
    
    test_file_path = r"E:\测试目录\1\653A7189.jpg"
    print(f"\n测试文件: {test_file_path}")
    
    config = Config()
    processor = ImageProcessor(config)
    
    print("\n调用get_windows_rating方法...")
    rating = processor.get_windows_rating(test_file_path)
    print(f"get_windows_rating返回值: {rating}")
    
    # 直接测试get_windows_rating方法的内部逻辑
    print("\n直接测试get_windows_rating方法的核心逻辑...")
    try:
        from win32com.client import Dispatch
        import os
        import re
        
        # 创建Shell对象用于访问文件属性
        shell = Dispatch("Shell.Application")
        
        # 获取文件所在目录的Folder对象
        folder_path = os.path.dirname(test_file_path)
        file_name = os.path.basename(test_file_path)
        
        folder = shell.NameSpace(folder_path)
        print(f"成功获取目录对象: {folder_path}")
        
        # 查找文件项
        item = None
        for i in range(0, folder.Items().Count):
            current_item = folder.Items().Item(i)
            if current_item.Name == file_name:
                item = current_item
                break
        
        if item:
            print(f"成功找到文件: {file_name}")
            
            # 检查索引19的属性
            rating_text = folder.GetDetailsOf(item, 19)
            print(f"索引19的内容: {rating_text}")
            
            # 解析星级评分
            if rating_text and "星级" in rating_text:
                match = re.search(r'(\d+)', rating_text)
                if match:
                    star_count = int(match.group(1))
                    print(f"成功解析星级: {star_count}星")
                else:
                    print("无法从星级文本中提取数字")
        else:
            print(f"找不到文件: {file_name}")
    except Exception as e:
        print(f"测试核心逻辑时出错: {e}")
        
except ImportError as e:
    print(f"导入模块失败: {e}")

print("\n测试完成")