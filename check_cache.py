#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查指定文件的元数据缓存是否存在
"""
import os
import hashlib

def check_metadata_cache(file_path):
    # 计算文件路径的哈希值（与image_processor.py中相同的方法）
    file_hash = hashlib.md5(file_path.encode('utf-8')).hexdigest()
    print(f'File hash: {file_hash}')
    
    # 构建缓存文件路径
    cache_dir = os.path.join('cache', 'metadata')
    cache_path = os.path.join(cache_dir, f'meta_{file_hash}.json')
    
    print(f'Cache directory: {cache_dir}')
    print(f'Cache file path: {cache_path}')
    print(f'Cache file exists: {os.path.exists(cache_path)}')
    
    # 如果缓存文件存在，读取其内容查看rating字段
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                metadata = eval(f.read())  # 使用eval代替json.load以避免可能的编码问题
                print(f'Cached rating: {metadata.get("rating", "Not found")}')
        except Exception as e:
            print(f'Error reading cache file: {e}')
    
if __name__ == "__main__":
    test_file_path = r'E:\测试目录\1\653A7189.jpg'
    check_metadata_cache(test_file_path)