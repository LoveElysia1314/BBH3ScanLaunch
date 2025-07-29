# network_utils.py
import requests
import os
import tempfile
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
        self.cache = {}  # 缓存下载的文件内容
        self.version_info = None  # 存储版本信息
        
        # 创建实例时自动获取远程文件
        self.fetch_remote_files()

    def fetch_from_source(self, url, timeout=5):
        """从单个源获取数据"""
        try:
            response = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
            if response.status_code == 200:
                return {
                    'content': response.content,
                    'text': response.text,
                    'json': response.json() if response.headers.get('content-type', '').startswith('application/json') else None,
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
                    self.cache['version.json'] = result['text']
                    self.version_info = json.loads(result['text'])  # 解析并存储版本信息
                    self.save_to_local(result['text'], "updates/version.json")
                    break
            
            # 获取changelog.txt
            changelog_urls = self.source_manager.get_source_urls(changelog_path, source_priority)
            for source_info in changelog_urls:
                result = self.fetch_from_source(source_info['url'], timeout=10)
                if result and result['success']:
                    self.cache['changelog.txt'] = result['text']
                    self.save_to_local(result['text'], "updates/changelog.txt")
                    break
            
            return True
        except Exception as e:
            print(f'[ERROR] 获取远程文件失败: {str(e)}')
            return False

    def download_update(self, progress_callback=None, source=None):
        """下载更新文件（根据version.json自动构建URL）"""
        if not self.version_info:
            # 如果没有版本信息，尝试重新获取
            if not self.fetch_remote_files():
                raise Exception("无法获取版本信息")
        
        app_info = self.version_info.get('app_info', {})
        package_name = app_info.get('package_name')
        version = app_info.get('version')
        
        if not package_name or not version:
            raise Exception("版本信息中缺少必要字段")
        
        # 获取自定义源配置
        custom_sources = self.version_info.get('sources', {}).get('download_url', {})
        
        # 生成标签（v+版本号）
        # tag = f"v{version}" if not version.startswith('v') else version
        
        # 使用最新版本teg
        tag = f"latest"
        # 获取下载URL列表
        source_priority = self.source_manager.normalize_source_input(source)
        download_urls = self.source_manager.get_release_urls(
            filename=package_name,
            tag=tag,
            source_priority=source_priority,
            custom_sources=custom_sources
        )
        
        # 尝试所有URL直到成功
        temp_file = None
        last_error = None
        
        for source_info in download_urls:
            try:
                print(f"[INFO] 尝试从 {source_info['name']} 下载更新...")
                response = requests.get(source_info['url'], stream=True, timeout=300)
                response.raise_for_status()
                
                temp_dir = tempfile.gettempdir()
                temp_file = os.path.join(temp_dir, "update_temp.exe")
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                
                with open(temp_file, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if progress_callback and total_size > 0:
                                progress = (downloaded / total_size) * 100
                                progress_callback(progress)
                
                print(f"[SUCCESS] 从 {source_info['name']} 下载成功")
                return temp_file
                
            except Exception as e:
                last_error = e
                print(f"[WARNING] 从 {source_info['name']} 下载失败: {str(e)}")
                continue
        
        # 所有源都失败
        error_msg = "所有下载源均失败"
        if last_error:
            error_msg += f"，最后错误: {str(last_error)}"
        raise Exception(error_msg)

# 全局网络管理实例
network_manager = NetworkManager()