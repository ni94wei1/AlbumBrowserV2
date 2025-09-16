#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
删除指定图片的元数据缓存文件
"""
import os

if __name__ == "__main__":
    # 从之前的调试信息中获取缓存文件路径
    cache_path = r'E:\测试目录\1\.album_cache\meta_a8a1ec74c8d14580342b1a1c93b5a6de.json'
    
    print(f"尝试删除缓存文件: {cache_path}")
    
    if os.path.exists(cache_path):
        try:
            os.remove(cache_path)
            print(f"成功删除缓存文件: {cache_path}")
        except Exception as e:
            print(f"删除缓存文件失败: {e}")
    else:
        print(f"缓存文件不存在: {cache_path}")
        
    # 也尝试删除可能存在的其他缓存目录
    # 检查是否有.cache目录
    alt_cache_path = r'E:\测试目录\1\.cache\meta_a8a1ec74c8d14580342b1a1c93b5a6de.json'
    if os.path.exists(alt_cache_path):
        try:
            os.remove(alt_cache_path)
            print(f"成功删除备用缓存文件: {alt_cache_path}")
        except Exception as e:
            print(f"删除备用缓存文件失败: {e}")
    
    # 检查根目录的cache目录
    root_cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cache', 'metadata')
    print(f"检查根目录缓存: {root_cache_dir}")
    
    # 列出root_cache_dir中的所有文件，看看是否有相关的缓存文件
    if os.path.exists(root_cache_dir):
        print("根目录缓存文件列表:")
        for file in os.listdir(root_cache_dir):
            print(f"  - {file}")
    else:
        print("根目录缓存不存在")