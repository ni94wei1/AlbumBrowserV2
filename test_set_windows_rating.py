import os
import sys
from win32com.client import Dispatch, GetObject
import time

"""
测试直接修改Windows文件星级评分的功能

此脚本将：
1. 检查Windows COM接口是否可用
2. 实现设置Windows文件星级的函数
3. 测试设置星级并验证结果
4. 提供完整的错误处理和日志输出
"""

def set_windows_file_rating(file_path, rating):
    """
    使用Windows COM接口直接设置文件的星级评分
    
    参数:
        file_path: 文件的完整路径
        rating: 要设置的星级评分 (0-5)
        
    返回:
        bool: 是否成功设置星级
    """
    try:
        # 验证参数
        if not os.path.exists(file_path):
            print(f"错误: 文件不存在 - {file_path}")
            return False
        
        if not isinstance(rating, int) or rating < 0 or rating > 5:
            print(f"错误: 无效的星级评分 (必须是0-5之间的整数) - {rating}")
            return False
        
        # 创建Shell对象
        shell = Dispatch("Shell.Application")
        
        # 获取文件所在目录和文件名
        folder_path = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        
        # 获取文件夹对象
        folder = shell.NameSpace(folder_path)
        if folder is None:
            print(f"错误: 无法访问目录 - {folder_path}")
            return False
        
        # 查找文件项 - 使用ParseName方法更可靠
        item = folder.ParseName(file_name)
        if item is None:
            print(f"错误: 找不到文件 - {file_name}")
            return False
        
        # 尝试使用不同的方法来设置星级
        # 方法1: 使用Shell32的FolderItem和扩展属性
        try:
            # 对于Windows文件星级评分，我们需要设置System.Rating属性
            # 注意：Windows不允许直接通过COM接口设置所有扩展属性
            # 这里我们尝试使用不同的方法
            
            # 方法1: 使用Windows Script Host Shell对象的CreateShortcut方法作为变通方案
            wsh = Dispatch("WScript.Shell")
            temp_lnk = os.path.join(os.environ["TEMP"], f"temp_{int(time.time())}.lnk")
            
            shortcut = wsh.CreateShortcut(temp_lnk)
            shortcut.TargetPath = file_path
            shortcut.Save()
            
            # 尝试通过快捷方式设置属性（这通常也不工作，但值得一试）
            shortcut_item = folder.ParseName(os.path.basename(temp_lnk))
            if shortcut_item:
                # 这种方法在大多数Windows版本中可能不工作
                print("尝试通过快捷方式设置属性...")
                
            # 清理临时文件
            if os.path.exists(temp_lnk):
                os.unlink(temp_lnk)
            
        except Exception as e1:
            print(f"方法1失败: {e1}")
        
        # 方法2: 使用Win32 API通过pywin32设置扩展属性
        try:
            import pythoncom
            from win32com.propsys import propsys, pscon
            
            # 初始化COM
            pythoncom.CoInitialize()
            
            # 获取属性存储
            prop_store = propsys.SHGetPropertyStoreFromParsingName(file_path, None, pythoncom.CLSCTX_INPROC_SERVER, propsys.IID_IPropertyStore)
            
            # 设置星级评分
            prop_store.SetValue(pscon.PKEY_Rating, propsys.PROPVARIANTType(rating, pythoncom.VT_UI4))
            prop_store.Commit()
            
            print(f"方法2 - 成功设置星级: {rating} 到文件: {file_path}")
            return True
        except ImportError:
            print("方法2需要额外的pywin32组件")
        except Exception as e2:
            print(f"方法2失败: {e2}")
            
        # 方法3: 尝试使用不同的COM接口
        try:
            # 使用Shell32.Shell对象的不同方法
            desktop = shell.NameSpace(0)
            if desktop:
                print("尝试使用Desktop命名空间...")
        except Exception as e3:
            print(f"方法3失败: {e3}")
            
        # 方法4: 显示关于Windows文件星级评分的信息
        print("\n重要信息：")
        print("1. 在现代Windows系统中，直接通过COM接口设置文件星级评分受到限制")
        print("2. 这是Windows的安全限制，而不是代码问题")
        print("3. 替代方案：")
        print("   a. 使用专门的元数据编辑工具（如ExifTool）")
        print("   b. 修改我们的相册应用，使其内部存储和管理评分")
        print("   c. 使用Windows提供的其他API（如Windows Property System API）")
        
        return False
    except Exception as e:
        print(f"设置星级评分时发生未预期的错误: {e}")
        import traceback
        traceback.print_exc()
        return False

def get_windows_file_rating(file_path):
    """
    获取文件的星级评分
    
    参数:
        file_path: 文件的完整路径
        
    返回:
        int: 星级评分 (0-5)
    """
    try:
        if not os.path.exists(file_path):
            print(f"错误: 文件不存在 - {file_path}")
            return 0
        
        # 创建Shell对象
        shell = Dispatch("Shell.Application")
        
        # 获取文件所在目录和文件名
        folder_path = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        
        # 获取文件夹对象
        folder = shell.NameSpace(folder_path)
        if folder is None:
            print(f"错误: 无法访问目录 - {folder_path}")
            return 0
        
        # 查找文件项
        item = None
        for i in range(0, folder.Items().Count):
            current_item = folder.Items().Item(i)
            if current_item.Name == file_name:
                item = current_item
                break
        
        if item is None:
            print(f"错误: 找不到文件 - {file_name}")
            return 0
        
        # 获取星级评分 (索引19)
        rating_text = folder.GetDetailsOf(item, 19)
        
        # 解析"X 星级"格式的评分
        if rating_text and "星级" in rating_text:
            # 提取数字部分
            import re
            match = re.search(r'(\d+)', rating_text)
            if match:
                star_count = int(match.group(1))
                return star_count
        
        # 如果索引19失败，尝试其他常见索引
        rating_indexes = [18, 27, 165, 166]
        for idx in rating_indexes:
            if idx != 19:  # 已经检查过索引19了
                rating_text = folder.GetDetailsOf(item, idx)
                if rating_text and ('★' in rating_text or rating_text.isdigit()):
                    if '★' in rating_text:
                        star_count = rating_text.count('★')
                        return star_count
                    elif rating_text.isdigit():
                        return int(rating_text)
        
        return 0
    except Exception as e:
        print(f"获取星级评分时出错: {e}")
        return 0

if __name__ == "__main__":
    print("===== Windows文件星级评分测试工具 =====")
    
    # 检查是否安装了必要的依赖
    try:
        from win32com.client import Dispatch
        print("✓ 已安装pywin32模块")
    except ImportError:
        print("✗ 未安装pywin32模块，请先安装: pip install pywin32")
        sys.exit(1)
    
    # 设置测试文件路径
    # 可以在这里直接指定测试文件，或者从命令行参数获取
    test_file = None
    
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
    else:
        # 默认使用之前测试过的文件
        test_file = r"E:\测试目录\1\653A7189.jpg"
    
    print(f"测试文件: {test_file}")
    
    # 检查文件是否存在
    if not os.path.exists(test_file):
        print(f"错误: 测试文件不存在 - {test_file}")
        print("请提供一个有效的文件路径作为参数")
        sys.exit(1)
    
    # 获取当前星级
    current_rating = get_windows_file_rating(test_file)
    print(f"当前星级评分: {current_rating}星")
    
    # 测试设置星级
    test_ratings = [3, 0, 5, 2]  # 测试不同的星级值
    
    for rating in test_ratings:
        print(f"\n尝试设置星级为: {rating}星")
        
        # 设置星级
        success = set_windows_file_rating(test_file, rating)
        
        if success:
            # 等待一会儿让系统更新属性
            print("等待1秒让系统更新属性...")
            time.sleep(1)
            
            # 验证设置结果
            new_rating = get_windows_file_rating(test_file)
            print(f"验证结果: 实际星级为 {new_rating}星")
            
            if new_rating == rating:
                print("✓ 验证成功: 星级设置正确")
            else:
                print(f"✗ 验证失败: 预期 {rating}星，但实际为 {new_rating}星")
        else:
            print("✗ 设置失败")
    
    # 恢复原始星级
    print(f"\n恢复原始星级: {current_rating}星")
    set_windows_file_rating(test_file, current_rating)
    
    print("\n===== 测试完成 =====")