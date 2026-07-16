#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
打包脚本 - 使用 7zip 压缩 dist 目录中的构建产物

功能：
1. 打包 CapsWriter-Offline（服务端+客户端）
2. 打包 CapsWriter-Offline-Client（仅客户端）
3. 智能排除模型文件（.onnx, .dll, .json 等），但保留说明文档
"""

import os
import zipfile
from pathlib import Path
from datetime import datetime


def should_include_file(file_path, is_client_only=False):
    """
    判断文件是否应该被打包

    打包规则：
    - 所有文件，除了 models/模型名/子目录/... 的内容
    - models/模型名/文件 会被打包（层级深度 == 2）
    - models/模型名/子目录/文件  不会被打包（层级深度 >= 3）
    - 如果是【仅客户端】打包：
        - 排除 core 目录下的所有 .dll 文件（客户端不需要本地识别引擎）
    """
    path = Path(file_path)
    parts = path.parts

    # 1. 客户端特殊排除逻辑
    if is_client_only:
        # 排除 core 中的 dll 文件
        if 'core' in parts and path.suffix.lower() == '.dll':
            return False

    # 2. 检查是否在 models 目录下
    if 'models' not in parts:
        return True  # 非 models 目录，全部打包

    # 找到 models 在路径中的位置
    try:
        models_index = parts.index('models')
    except ValueError:
        return True

    # 排除 models 目录下的所有 .zip 文件（原始压缩包不打包）
    if 'models' in parts and path.suffix.lower() == '.zip' or  path.suffix.lower() == '.cfg':
        return False

    # models/模型名/子目录/... 的深度 >= 3 不打包
    depth = len(parts) - models_index

    if depth >= 4:  # models/模型名/子目录/文件 或更深
        return False
    else:  # models/模型名/文件 或更浅
        return True


def create_file_list(dist_folder, output_file='file_list.txt', is_client_only=False):
    """
    创建要打包的文件列表

    7zip 使用 @参数从文件读取列表
    每行一个文件路径（相对于 dist 父目录）
    """
    files = []

    # 遍历 dist 目录，收集所有要打包的文件
    dist_path = Path(dist_folder)
    if not dist_path.exists():
        return files, None

    for root, dirs, filenames in os.walk(dist_path):
        # 排除不需要打包的文件夹
        dirs[:] = [d for d in dirs if d not in ('__pycache__', '.vscode', '.git')]

        for filename in filenames:
            file_path = os.path.join(root, filename)
            if should_include_file(file_path, is_client_only):
                # 计算相对于 dist 父目录的路径
                rel_path = os.path.relpath(file_path, dist_path.parent)
                files.append(rel_path)

    if not files:
        return files, None

    # 写入文件列表
    list_file = Path(output_file)
    list_file.write_text('\n'.join(files), encoding='utf-8')

    return files, list_file


def package_with_zip(source_dir, output_zip, file_list_file):
    """使用 Python 标准库生成 ZIP，无需额外安装 7-Zip。"""
    source_path = Path(source_dir)
    if not source_path.exists():
        raise FileNotFoundError(f"源目录不存在: {source_dir}")

    # 确保输出目录存在
    output_path = Path(output_zip)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    dist_dir = source_path.parent
    relative_files = Path(file_list_file).read_text(encoding='utf-8').splitlines()
    files_count = len(relative_files)

    print(f"\n正在打包: {source_path.name}")
    print(f"输出文件: {output_zip}")
    print(f"打包文件数: {files_count}")
    print(f"工作目录: {dist_dir.absolute()}")

    if output_path.exists():
        output_path.unlink()
    with zipfile.ZipFile(
        output_path,
        mode='w',
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for relative_file in relative_files:
            source_file = dist_dir / relative_file
            archive.write(source_file, arcname=relative_file)

    print("\n打包成功！")
    print(f"压缩包信息: {files_count} 个文件")


def main():
    """主函数"""
    dist_dir = Path('dist')

    # 检查 dist 目录
    if not dist_dir.exists():
        print(f"错误: dist 目录不存在")
        print(f"请先运行 PyInstaller 构建: pyinstaller build.spec")
        return 1

    print("=" * 60)
    print("CapsWriter-Offline 打包脚本")
    print("=" * 60)

    # 构建输出目录
    release_dir = Path('release')
    release_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d")

    # 打包配置列表
    packages = []

    # 检查 CapsWriter-Offline（服务端+客户端）
    server_dist = dist_dir / 'CapsWriter-Offline'
    if server_dist.exists():
        packages.append({
            'source': server_dist,
            'output': release_dir / f'CapsWriter-Offline-{timestamp}.zip',
            'name': '服务端+客户端'
        })

    # 检查 CapsWriter-Offline-Client（仅客户端）
    client_dist = dist_dir / 'CapsWriter-Offline-Client'
    if client_dist.exists():
        packages.append({
            'source': client_dist,
            'output': release_dir / f'CapsWriter-Offline-Client-{timestamp}.zip',
            'name': '仅客户端'
        })

    if not packages:
        print(f"\n错误: dist 目录中没有找到构建产物")
        print(f"请先运行 PyInstaller 构建:")
        print(f"  pyinstaller build.spec")
        print(f"  pyinstaller build-client.spec")
        return 1

    print(f"\n找到 {len(packages)} 个待打包的构建产物")

    # 逐个打包
    success_count = 0
    for idx, pkg in enumerate(packages):
        try:
            print(f"\n{'=' * 60}")
            print(f"打包: {pkg['name']}")
            print(f"{'=' * 60}")

            # 生成唯一的文件列表名（避免冲突）
            list_file_name = f'file_list_{idx}.txt'

            # 生成文件列表
            is_client_only = pkg['source'].name == 'CapsWriter-Offline-Client'
            files, list_file = create_file_list(pkg['source'], list_file_name, is_client_only)

            if not files:
                print(f"\n警告: 没有找到要打包的文件")
                continue

            print(f"文件列表: {list_file}")

            # 打包
            package_with_zip(
                pkg['source'],
                pkg['output'],
                list_file
            )

            success_count += 1

            # 删除临时文件列表
            try:
                list_file.unlink()
                print(f"已删除临时文件列表: {list_file}")
            except Exception as cleanup_error:
                print(f"警告: 无法删除临时文件列表 {list_file}: {cleanup_error}")

        except Exception as e:
            print(f"\n打包失败: {e}")

    # 总结
    print(f"\n{'=' * 60}")
    print(f"打包完成: {success_count}/{len(packages)} 成功")
    print(f"{'=' * 60}")
    print(f"\n输出目录: {release_dir.absolute()}")

    # 列出生成的文件
    if success_count > 0:
        print(f"\n生成的文件:")
        for file in sorted(release_dir.glob('*.zip')):
            size_mb = file.stat().st_size / (1024 * 1024)
            print(f"  {file.name} ({size_mb:.1f} MB)")

    return 0 if success_count == len(packages) else 1


if __name__ == '__main__':
    raise SystemExit(main())
