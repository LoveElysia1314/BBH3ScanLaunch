import asyncio
import requests

async def sendPost(target, data, noReturn=False):
    try:
        session = requests.Session()
        session.trust_env = False
        res = session.post(url=target, data=data)
        if noReturn:
            return
        if res is None:
            print("[INFO] 请求错误，正在重试...")
            return await sendPost(target, data, noReturn)
        return res.json()
    except Exception as e:
        print(f"[ERROR] POST 请求失败: {e}")
        return None

async def sendGet(target, default_ret=None):
    try:
        session = requests.Session()
        session.trust_env = False
        res = session.get(url=target)
        if res is None:
            print("[INFO] 请求错误，正在重试...")
            return await sendGet(target, default_ret)
        return res.json()
    except Exception as e:
        print(f"[ERROR] GET 请求失败: {e}")
        return default_ret

async def sendGetRaw(target, default_ret=None):
    try:
        session = requests.Session()
        session.trust_env = False
        res = session.get(url=target)
        if res is None:
            print("[INFO] 请求错误，正在重试...")
            return await sendGetRaw(target, default_ret)
        return res.text
    except Exception as e:
        print(f"[ERROR] GET 原始请求失败: {e}")
        return default_ret

async def sendBiliPost(url, data):
    header = {
        "User-Agent": "Mozilla/5.0 BSGameSDK",
        "Content-Type": "application/x-www-form-urlencoded",
        "Host": "line1-sdk-center-login-sh.biligame.net"
    }
    try:
        session = requests.Session()
        session.trust_env = False
        res = session.post(url=url, data=data, headers=header)
        if res is None:
            print("[INFO] 请求错误，3s后重试...")
            await asyncio.sleep(3)
            return await sendBiliPost(url, data)
        # print("[DEBUG]", res.json(),sep=" ")
        return res.json()
    except Exception as e:
        print(f"[ERROR] B站POST请求失败: {e}")
        return None


# network_utils.py
import requests
import json
import os
import sys
import tempfile
import subprocess
import threading
from urllib.parse import urlparse
import concurrent.futures
import time
from packaging import version

class NetworkManager:
    def __init__(self):
        self.current_version = "1.1.0"
        # CDN镜像源列表
        self.cdn_mirrors = [
            "https://cdn.jsdelivr.net",
            "https://gcore.jsdelivr.net", 
            "https://fastly.jsdelivr.net",
            "https://jsd.onmicrosoft.cn",
            "https://jsd.cdn.zzko.cn"
        ]
    
    def set_current_version(self, version_str):
        """设置当前程序版本"""
        self.current_version = version_str
    
    def fetch_from_multiple_sources(self, base_url, timeout=5):
        """
        从多个CDN源并行获取数据，返回最快的成功响应
        """
        print(f'[INFO] 开始从多个源获取: {base_url}')
        
        def fetch_single_source(mirror_url):
            try:
                start_time = time.time()
                response = requests.get(
                    mirror_url,
                    timeout=timeout,
                    headers={"User-Agent": "Mozilla/5.0"}
                )
                if response.status_code == 200:
                    return {
                        'url': mirror_url,
                        'content': response.content,
                        'text': response.text,
                        'json': response.json() if response.headers.get('content-type', '').startswith('application/json') else None,
                        'time': time.time() - start_time,
                        'success': True,
                        'status_code': response.status_code
                    }
            except Exception as e:
                pass
            return {'url': mirror_url, 'success': False}
        
        # 构造所有镜像URL
        mirror_urls = [f"{mirror}{urlparse(base_url).path}" for mirror in self.cdn_mirrors]
        
        # 并行请求
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(fetch_single_source, url) for url in mirror_urls]
            results = []
            
            # 处理完成的请求
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if not result['success']:
                    continue
                
                results.append(result)
                # 返回第一个成功的响应（最快的）
                if results:
                    fastest = min(results, key=lambda x: x['time'])
                    print(f'[INFO] 使用源: {fastest["url"]}, 耗时: {fastest["time"]:.2f}秒')
                    return fastest
        
        print('[WARNING] 所有源均无法访问')
        return None
    
    def get_oa_token(self):
        """获取OA token和游戏版本"""
        original_url = "https://cdn.jsdelivr.net/gh/LoveElysia1314/BBH3ScanLaunch@latest/oa_token.json"
        result = self.fetch_from_multiple_sources(original_url)
        
        if result and result['success']:
            try:
                if result['json']:
                    data = result['json']
                else:
                    data = json.loads(result['text'])
                
                oa_token = data.get("oa_token", "e257aaa274fb2239094cbe64d9f5ee3e")
                bh_ver = data.get("bh_ver", "8.4.0")
                print('[INFO] OA Token获取成功')
                return oa_token, bh_ver
            except Exception as e:
                print(f'[WARNING] 解析OA Token失败: {e}')
        
        print('[WARNING] 使用默认OA Token')
        return "e257aaa274fb2239094cbe64d9f5ee3e", "8.4.0"
    
    def check_program_update(self):
        """检查程序是否有新版本"""
        try:
            # 获取远程版本信息
            version_url = "https://cdn.jsdelivr.net/gh/LoveElysia1314/BBH3ScanLaunch@latest/updates/version.json"
            result = self.fetch_from_multiple_sources(version_url, timeout=10)
            
            if result and result['success']:
                if result['json']:
                    remote_data = result['json']
                else:
                    remote_data = json.loads(result['text'])
                
                remote_version = remote_data.get("version", "0.0.0")
                
                # 比较版本号
                if version.parse(remote_version) > version.parse(self.current_version):
                    return {
                        "has_update": True,
                        "version": remote_version,
                        "download_url": remote_data.get("download_url"),
                        "changelog": remote_data.get("changelog", ""),
                        "size": remote_data.get("size", "未知"),
                        "release_date": remote_data.get("release_date", "")
                    }
                else:
                    return {"has_update": False}
            else:
                return {"has_update": False, "error": "无法获取版本信息"}
                
        except Exception as e:
            print(f'[ERROR] 检查更新失败: {str(e)}')
            return {"has_update": False, "error": str(e)}
    
    def download_update(self, download_url, progress_callback=None):
        """下载更新文件（支持多源CDN）"""
        try:
            print(f'[INFO] 开始下载更新文件: {download_url}')
            
            # 使用多源下载
            result = self.fetch_from_multiple_sources(download_url, timeout=300)
            
            if result and result['success']:
                temp_dir = tempfile.gettempdir()
                temp_file = os.path.join(temp_dir, "update_temp.exe")
                
                # 保存文件
                with open(temp_file, 'wb') as f:
                    f.write(result['content'])
                
                print(f'[INFO] 文件下载完成: {temp_file}')
                return temp_file
            else:
                raise Exception("所有CDN源都无法访问")
            
        except Exception as e:
            print(f'[ERROR] 下载更新失败: {str(e)}')
            raise
    
    def download_file_with_progress(self, download_url, progress_callback=None):
        """带进度条的文件下载（用于大文件）"""
        try:
            temp_dir = tempfile.gettempdir()
            temp_file = os.path.join(temp_dir, "update_temp.exe")
            
            # 使用多源下载，但逐个尝试直到成功
            for mirror in self.cdn_mirrors:
                try:
                    mirror_url = f"{mirror}{urlparse(download_url).path}"
                    print(f'[INFO] 尝试下载源: {mirror_url}')
                    
                    response = requests.get(mirror_url, stream=True, timeout=300)
                    response.raise_for_status()
                    
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
                    
                    print(f'[INFO] 文件下载完成: {temp_file}')
                    return temp_file
                    
                except Exception as e:
                    print(f'[WARNING] 源 {mirror} 下载失败: {e}')
                    continue
            
            raise Exception("所有CDN源都无法访问")
            
        except Exception as e:
            print(f'[ERROR] 下载更新失败: {str(e)}')
            raise
    
    def install_update(self, new_file_path):
        """安装更新（替换当前程序）"""
        try:
            current_exe = sys.executable
            current_dir = os.path.dirname(current_exe)
            
            # 创建更新脚本
            bat_content = f'''@echo off
                timeout /t 2 /nobreak >nul
                cd /d "{current_dir}"
                del "{current_exe}"
                move "{new_file_path}" "{current_exe}"
                start "" "{current_exe}"
                        '''
            
            # 写入临时bat文件
            bat_path = os.path.join(tempfile.gettempdir(), "update.bat")
            with open(bat_path, 'w') as f:
                f.write(bat_content)
            
            # 执行更新脚本
            subprocess.Popen(bat_path, shell=True)
            
            return True
            
        except Exception as e:
            print(f'[ERROR] 安装更新失败: {str(e)}')
            return False

# 全局网络管理实例
network_manager = NetworkManager()