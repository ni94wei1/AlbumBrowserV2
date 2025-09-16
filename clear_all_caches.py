#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
清理所有图片的元数据缓存文件，确保星级评分正确显示
"""
import os
import sys
import shutil

def find_and_remove_cache_files(start_dir):
    """递归查找并删除所有相册缓存文件"""
    if not os.path.exists(start_dir):
        print(f"目录不存在: {start_dir}")
        return
    
    print(f"开始清理缓存文件，从目录: {start_dir}")
    
    cache_count = 0
    album_cache_dirs = 0
    
    # 遍历所有目录和文件
    for root, dirs, files in os.walk(start_dir):
        # 检查是否有.album_cache目录
        if '.album_cache' in dirs:
            cache_dir = os.path.join(root, '.album_cache')
            album_cache_dirs += 1
            
            try:
                # 获取.cache_dir中的文件数量
                cache_files = os.listdir(cache_dir)
                file_count = len(cache_files)
                
                # 删除整个.album_cache目录
                shutil.rmtree(cache_dir)
                cache_count += file_count
                print(f"已删除缓存目录: {cache_dir}, 包含{file_count}个文件")
            except Exception as e:
                print(f"删除缓存目录失败 {cache_dir}: {e}")
    
    print(f"\n清理完成！")
    print(f"删除了 {album_cache_dirs} 个.album_cache目录")
    print(f"总共删除了 {cache_count} 个缓存文件")

if __name__ == "__main__":
    # 检查是否提供了目录参数
    if len(sys.argv) > 1:
        start_directory = sys.argv[1]
    else:
        # 默认清理E:\测试目录
        start_directory = r'E:\测试目录'
        
    print("===== 相册缓存清理工具 =====")
    print(f"将清理目录: {start_directory}")
    
    # 自动清理，不需要用户确认
    find_and_remove_cache_files(start_directory)
    
    print("==========================")