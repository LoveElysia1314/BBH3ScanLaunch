# network_utils.py
import requests
import os
import webbrowser
import json
from urllib.parse import urljoin

class SourceManager:
    """管理不同代码托管平台的源"""
    def __init__(self):
        # 保留gitee和github源，并添加release类型
        self.sources = {
            'gitee': {
                'base_url': 'https://gitee.com/{username}/{repo}/raw/{branch}/',
                'release_url': 'https://gitee.com/{username}/{repo}/releases/download/{tag}/{filename}',
                'type': 'direct'
            },
            'github': {
                'base_url': 'https://raw.githubusercontent.com/{username}/{repo}/{branch}/',
                'release_url': 'https://github.com/{username}/{repo}/releases/download/{tag}/{filename}',
                'type': 'direct'
            }
        }
        # 默认源优先级列表
        self.default_priority = ['gitee', 'github']

    def get_source_urls(self, path, source_priority=None, username="LoveElysia1314", repo="BBH3ScanLaunch", branch="main"):
        """根据优先级生成不同源的完整 URL"""
        if source_priority is None:
            source_priority = self.default_priority

        urls = []
        for source_name in source_priority:
            if source_name in self.sources:
                source_info = self.sources[source_name]
                base_url = source_info['base_url'].format(username=username, repo=repo, branch=branch)
                full_url = urljoin(base_url, path.lstrip('/'))
                urls.append({'name': source_name, 'url': full_url, 'type': source_info['type']})
        return urls

    def get_release_urls(self, filename, tag="latest", source_priority=None, username="LoveElysia1314", repo="BBH3ScanLaunch", custom_sources=None):
        """生成不同源的发布下载URL"""
        if source_priority is None:
            source_priority = self.default_priority

        urls = []
        
        # 添加平台源
        for source_name in source_priority:
            if source_name in self.sources:
                source_info = self.sources[source_name]
                release_url = source_info['release_url'].format(
                    username=username, 
                    repo=repo, 
                    tag=tag,
                    filename=filename
                )
                urls.append({'name': source_name, 'url': release_url, 'type': 'release'})
        
        # 添加自定义源
        if custom_sources:
            for source_name, url_template in custom_sources.items():
                # 替换URL中的版本变量
                formatted_url = url_template.replace("{tag}", tag).replace("{filename}", filename)
                urls.append({'name': source_name, 'url': formatted_url, 'type': 'custom'})
        
        return urls

    def normalize_source_input(self, source_input):
        """标准化源输入，支持字符串或列表"""
        if isinstance(source_input, str):
            if source_input in ['gitee', 'github']:
                return [source_input]
            return self.default_priority
        elif isinstance(source_input, list):
            return [s for s in source_input if s in self.default_priority]
        else:
            return self.default_priority

class NetworkManager:
    def __init__(self):
        self.source_manager = SourceManager()
        self.version_info = None  # 存储版本信息
        
        # 创建实例时自动获取远程文件
        self.fetch_remote_files()

    def fetch_from_source(self, url, timeout=5):
        """从单个源获取数据"""
        try:
            response = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
            if response.status_code == 200:
                return {
                    'text': response.text,  # 只保留实际使用的字段
                    'success': True,
                    'status_code': response.status_code
                }
        except Exception:
            pass
        return {'success': False}

    def save_to_local(self, content, file_path):
        """保存内容到本地文件"""
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except Exception as e:
            print(f'[ERROR] 保存文件失败: {str(e)}')
            return False

    def fetch_remote_files(self, source=None):
        """从远程获取version.json和changelog.txt"""
        try:
            source_priority = self.source_manager.normalize_source_input(source)
            version_path = "updates/version.json"
            changelog_path = "updates/changelog.txt"
            
            # 获取version.json
            version_urls = self.source_manager.get_source_urls(version_path, source_priority)
            for source_info in version_urls:
                result = self.fetch_from_source(source_info['url'], timeout=10)
                if result and result['success']:
                    self.version_info = json.loads(result['text'])  # 解析并存储版本信息
                    self.save_to_local(result['text'], "updates/version.json")
                    break
            
            # 获取changelog.txt
            changelog_urls = self.source_manager.get_source_urls(changelog_path, source_priority)
            for source_info in changelog_urls:
                result = self.fetch_from_source(source_info['url'], timeout=10)
                if result and result['success']:
                    self.save_to_local(result['text'], "updates/changelog.txt")
                    break
            
            return True
        except Exception as e:
            print(f'[ERROR] 获取远程文件失败: {str(e)}')
            return False

    def open_browser_for_download(self, package_name="BBH3ScanLaunch_Setup.exe", source=None):
        """
        使用浏览器打开指定源的下载链接
        
        参数:
            package_name: 要下载的文件名
            source: 指定的下载源名称（必须提供）
        
        工作流程:
            1. 验证必须指定下载源
            2. 获取版本信息（包含自定义源配置）
            3. 检查是否为自定义源（在version.json中定义）
            4. 如果是自定义源，直接获取对应的URL
            5. 如果是平台源（gitee/github），生成对应的发布URL
            6. 使用浏览器打开下载链接
        
        异常:
            如果没有找到有效的下载源，抛出异常
        """
        # 1. 验证必须指定下载源
        if source is None:
            raise ValueError("必须指定下载源（source参数不能为None）")
        
        # 2. 获取版本信息
        if not self.version_info:
            if not self.fetch_remote_files():
                raise Exception("无法获取版本信息")
        
        # 3. 检查是否为自定义源
        custom_sources = self.version_info.get('sources', {}).get('download_url', {})
        
        if source in custom_sources:
            # 4. 直接使用自定义源URL（不需要格式化）
            download_url = custom_sources[source]
            print(f"[INFO] 使用自定义源 '{source}': {download_url}")
        else:
            # 5. 生成平台源的发布URL
            download_urls = self.source_manager.get_release_urls(
                filename=package_name,
                tag="latest",
                source_priority=[source],  # 单个源
                custom_sources=None  # 不包含自定义源
            )
            
            if not download_urls:
                raise Exception(f"找不到有效的下载源: '{source}'")
            
            # 取第一个匹配的URL
            download_url = download_urls[0]['url']
            print(f"[INFO] 使用平台源 '{source}': {download_url}")
        
        # 6. 使用浏览器打开下载链接
        print(f"[INFO] 正在打开浏览器下载: {download_url}")
        try:
            webbrowser.open(download_url)
            return True
        except Exception as e:
            print(f"[ERROR] 无法打开浏览器: {str(e)}")
            return False

# 全局网络管理实例
network_manager = NetworkManager()