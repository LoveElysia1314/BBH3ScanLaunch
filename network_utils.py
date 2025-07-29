# network_utils.py
import requests
import json
import os
import sys
import tempfile
from urllib.parse import urljoin
from version_utils import version_manager

class SourceManager:
    """管理不同代码托管平台的源"""
    def __init__(self):
        # 只保留gitee和github源
        self.sources = {
            'gitee': {
                'base_url': 'https://gitee.com/{username}/{repo}/raw/{branch}/',
                'type': 'direct'
            },
            'github': {
                'base_url': 'https://raw.githubusercontent.com/{username}/{repo}/{branch}/',
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

    def get_oa_token(self, source=None):
        """获取OA token和游戏版本"""
        source_priority = self.source_manager.normalize_source_input(source)
        urls_to_try = self.source_manager.get_source_urls("updates/version.json", source_priority)
        
        for source_info in urls_to_try:
            result = self.fetch_from_source(source_info['url'])
            if result and result['success']:
                try:
                    data = result['json'] or json.loads(result['text'])
                    oa_info = data.get("oa_info", {})
                    return (
                        oa_info.get("oa_token", "e257aaa274fb2239094cbe64d9f5ee3e"),
                        oa_info.get("bh_ver", "8.4.0")
                    )
                except Exception as e:
                    print(f'[WARNING] 解析OA Token失败: {e}')
        return "e257aaa274fb2239094cbe64d9f5ee3e", "8.4.0"

    def check_program_update(self, source=None):
        """检查程序更新"""
        try:
            source_priority = self.source_manager.normalize_source_input(source)
            version_path = "updates/version.json"
            urls_to_try = self.source_manager.get_source_urls(version_path, source_priority)
            
            for source_info in urls_to_try:
                result = self.fetch_from_source(source_info['url'], timeout=10)
                if result and result['success']:
                    try:
                        data = result['json'] or json.loads(result['text'])
                        app_info = data.get("app_info", {})
                        remote_version = app_info.get("version", "0.0.0")
                        
                        if remote_version > version_manager.get_current_version():
                            return self._prepare_update_info(data, source_info)
                        else:
                            print(f"[INFO] 已是最新版本: {version_manager.get_current_version()}")
                            return {"has_update": False, "version": remote_version}
                    except Exception as e:
                        print(f'[ERROR] 解析版本信息失败: {e}')
            return {"has_update": False, "error": "所有源均无法访问"}
        except Exception as e:
            print(f'[ERROR] 检查更新失败: {str(e)}')
            return {"has_update": False, "error": f"检查更新失败: {str(e)}"}

    def _prepare_update_info(self, remote_data, source_info):
        """准备更新信息"""
        app_info = remote_data.get("app_info", {})
        sources_dict = remote_data.get("sources", {})
        
        # 构建下载URL
        download_url = sources_dict.get("download_url", {}).get(source_info['name']) or app_info.get("download_path", "")
        if download_url and not download_url.startswith(('http://', 'https://')):
            base_url = '/'.join(source_info['url'].split('/')[:-1]) + '/'
            download_url = urljoin(base_url, download_url.lstrip('/'))
        
        # 构建更新日志URL
        changelog_url = sources_dict.get("changelog", {}).get(source_info['name']) or app_info.get("changelog_path", "")
        if changelog_url and not changelog_url.startswith(('http://', 'https://')):
            base_url = '/'.join(source_info['url'].split('/')[:-1]) + '/'
            changelog_url = urljoin(base_url, changelog_url.lstrip('/'))
        
        # 获取更新日志内容
        changelog_content = ""
        if changelog_url:
            changelog_result = self.fetch_from_source(changelog_url, timeout=30)
            if changelog_result and changelog_result['success']:
                changelog_content = changelog_result.get('text', '')
        
        return {
            "has_update": True,
            "version": app_info.get("version", "0.0.0"),
            "download_url": download_url,
            "changelog": changelog_content,
            "size": app_info.get("size", "未知"),
            "release_date": app_info.get("release_date", ""),
            "used_source": source_info['name']
        }

    def download_update(self, download_url, progress_callback=None, source=None):
        """下载更新文件"""
        try:
            if download_url.startswith(('http://', 'https://')):
                response = requests.get(download_url, stream=True, timeout=300)
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
                
                return temp_file
            else:
                raise Exception("无效的下载URL")
        except Exception as e:
            print(f'[ERROR] 下载更新失败: {str(e)}')
            raise

    def install_update(self, new_file_path):
        """安装更新"""
        try:
            current_exe = sys.executable
            current_dir = os.path.dirname(current_exe)
            
            bat_content = f'''@echo off
cd /d "{current_dir}"
del "{current_exe}"
move "{new_file_path}" "{current_exe}"
start "" "{current_exe}"
exit
'''
            bat_path = os.path.join(tempfile.gettempdir(), "update.bat")
            with open(bat_path, 'w') as f:
                f.write(bat_content)
                
            os.startfile(bat_path)
            return True
        except Exception as e:
            print(f'[ERROR] 安装更新失败: {str(e)}')
            return False

# 全局网络管理实例
network_manager = NetworkManager()