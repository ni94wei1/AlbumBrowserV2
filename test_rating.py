import os
import sys
# 使用win32com.client来获取Windows文件星级评分
from win32com.client import Dispatch

class WindowsFileRatingTester:
    def __init__(self):
        try:
            # 创建Shell对象用于访问文件属性
            self.shell = Dispatch("Shell.Application")
            self.com_available = True
        except Exception as e:
            print(f"无法创建Shell对象: {e}")
            self.com_available = False
    
    def get_file_rating(self, file_path):
        """使用Shell对象获取Windows文件星级评分"""
        if not self.com_available:
            return -1
        
        try:
            # 获取文件所在目录的Folder对象
            folder_path = os.path.dirname(file_path)
            file_name = os.path.basename(file_path)
            
            folder = self.shell.NameSpace(folder_path)
            if folder is None:
                print(f"无法访问目录: {folder_path}")
                return -1
            
            # 查找文件项
            item = None
            for i in range(0, folder.Items().Count):
                current_item = folder.Items().Item(i)
                if current_item.Name == file_name:
                    item = current_item
                    break
            
            if item is None:
                print(f"找不到文件: {file_name}")
                return -1
            
            # 从测试结果看，星级评分在索引19
            print("重点检查索引19的星级属性...")
            rating_text = folder.GetDetailsOf(item, 19)
            print(f"索引19的内容: {rating_text}")
            
            # 解析"X 星级"格式的评分
            if rating_text and "星级" in rating_text:
                # 提取数字部分
                try:
                    # 尝试从字符串中提取数字
                    import re
                    match = re.search(r'(\d+)', rating_text)
                    if match:
                        star_count = int(match.group(1))
                        print(f"成功解析星级: {star_count}星")
                        return star_count
                    else:
                        print("无法从星级文本中提取数字")
                except Exception as e:
                    print(f"解析星级时出错: {e}")
            
            # 如果索引19失败，尝试其他常见索引
            rating_indexes = [18, 27, 165, 166]
            for idx in rating_indexes:
                if idx != 19:  # 已经检查过索引19了
                    rating_text = folder.GetDetailsOf(item, idx)
                    print(f"检查索引 {idx}: {rating_text}")
                    if rating_text and ('★' in rating_text or rating_text.isdigit()):
                        if '★' in rating_text:
                            star_count = rating_text.count('★')
                            return star_count
                        elif rating_text.isdigit():
                            return int(rating_text)
            
            return 0
                
        except Exception as e:
            print(f"获取星级评分时出错: {e}")
            return -1

if __name__ == "__main__":
    # 测试文件路径
    test_file_path = r"E:\测试目录\1\653A7189.jpg"
    
    print(f"测试文件: {test_file_path}")
    print(f"文件是否存在: {os.path.exists(test_file_path)}")
    
    # 如果命令行提供了文件路径参数，则使用它
    if len(sys.argv) > 1:
        test_file_path = sys.argv[1]
        print(f"使用命令行提供的文件路径: {test_file_path}")
    
    tester = WindowsFileRatingTester()
    rating = tester.get_file_rating(test_file_path)
    
    if rating >= 0:
        print(f"\n最终文件星级评分: {rating}星")
    else:
        print("\n无法获取星级评分")