# network_utils.py
import requests
import os
import webbrowser
import json
import logging
from urllib.parse import urljoin
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional


class SourceManager:
    """管理不同代码托管平台的源"""

    def __init__(self):
        # 保留gitee和github源，并添加release类型
        self.sources = {
            "gitee": {
                "base_url": "https://gitee.com/{username}/{repo}/raw/{branch}/",
                "release_url": "https://gitee.com/{username}/{repo}/releases/download/{tag}/{filename}",
                "type": "direct",
            },
            "github": {
                "base_url": "https://raw.githubusercontent.com/{username}/{repo}/{branch}/",
                "release_url": "https://github.com/{username}/{repo}/releases/download/{tag}/{filename}",
                "type": "direct",
            },
        }
        # 默认源优先级列表
        self.default_priority = ["gitee", "github"]

    def get_source_urls(
        self,
        path,
        source_priority=None,
        username="LoveElysia1314",
        repo="BBH3ScanLaunch",
        branch="main",
    ):
        """根据优先级生成不同源的完整 URL"""
        if source_priority is None:
            source_priority = self.default_priority

        urls = []
        for source_name in source_priority:
            if source_name in self.sources:
                source_info = self.sources[source_name]
                base_url = source_info["base_url"].format(
                    username=username, repo=repo, branch=branch
                )
                full_url = urljoin(base_url, path.lstrip("/"))
                urls.append(
                    {"name": source_name, "url": full_url, "type": source_info["type"]}
                )
        return urls

    def get_release_urls(
        self,
        filename,
        tag="latest",
        source_priority=None,
        username="LoveElysia1314",
        repo="BBH3ScanLaunch",
        custom_sources=None,
    ):
        """仅生成不同源的发布下载URL（不做网络请求）"""
        if source_priority is None:
            source_priority = self.default_priority

        urls: List[Dict[str, str]] = []

        # 平台源
        for source_name in source_priority:
            if source_name in self.sources:
                source_info = self.sources[source_name]
                release_url = source_info["release_url"].format(
                    username=username, repo=repo, tag=tag, filename=filename
                )
                urls.append(
                    {"name": source_name, "url": release_url, "type": "release"}
                )

        # 自定义源（如果提供）
        if custom_sources:
            for source_name, url_template in custom_sources.items():
                # 兼容直接URL或带占位符的模板
                formatted_url = (
                    url_template.replace("{tag}", tag).replace("{filename}", filename)
                    if isinstance(url_template, str)
                    else None
                )
                if not formatted_url or not formatted_url.startswith("http"):
                    logging.warning(
                        f"自定义源 '{source_name}' 的 URL 无效: {url_template}"
                    )
                    continue
                urls.append(
                    {"name": source_name, "url": formatted_url, "type": "custom"}
                )

        # 去重（按URL）保持顺序
        seen = set()
        deduped = []
        for u in urls:
            if u["url"] in seen:
                continue
            seen.add(u["url"])
            deduped.append(u)
        return deduped

    def normalize_source_input(self, source_input):
        """标准化源输入，支持字符串或列表"""
        if isinstance(source_input, str):
            if source_input in ["gitee", "github"]:
                return [source_input]
            return self.default_priority
        elif isinstance(source_input, list):
            return [s for s in source_input if s in self.default_priority]
        else:
            return self.default_priority


class LinkProber:
    """链接探测器：检测可达性、RTT与简单吞吐"""

    def __init__(self, user_agent: str = "Mozilla/5.0"):
        self.headers = {"User-Agent": user_agent}

    def probe(self, url: str, timeout: float = 6.0) -> Dict:
        start = time.time()
        final_url = url
        status = None
        error = None
        rtt = None
        tput_kbps = None

        try:
            # 1) 尝试 HEAD（允许重定向）
            resp = requests.head(
                url, timeout=timeout, allow_redirects=True, headers=self.headers
            )
            status = resp.status_code
            final_url = resp.url
            first_byte_time = time.time()
            rtt = max(0.0, first_byte_time - start)

            if status >= 400 or status is None:
                raise requests.RequestException(f"HEAD bad status: {status}")

            # 2) 可选：小范围 GET 估计吞吐
            try:
                rng_headers = {**self.headers, "Range": "bytes=0-16383"}  # 16KB
                gstart = time.time()
                g = requests.get(
                    final_url, timeout=timeout, headers=rng_headers, stream=True
                )
                read_bytes = 0
                chunk_start = time.time()
                for chunk in g.iter_content(chunk_size=4096):
                    if not chunk:
                        break
                    read_bytes += len(chunk)
                    if read_bytes >= 16 * 1024:
                        break
                g.close()
                gelapsed = max(1e-6, time.time() - chunk_start)
                tput_kbps = (read_bytes / 1024.0) / gelapsed
            except Exception:
                # 吞吐测量失败不影响可达性
                pass

            return {
                "original_url": url,
                "final_url": final_url,
                "reachable": True,
                "status_code": status,
                "rtt": rtt,
                "tput_kbps": tput_kbps,
                "error": None,
            }
        except Exception as e:
            error = str(e)
            return {
                "original_url": url,
                "final_url": final_url,
                "reachable": False,
                "status_code": status or 0,
                "rtt": rtt,
                "tput_kbps": tput_kbps,
                "error": error,
            }


class MultiSourceSelector:
    """多源选择器：并发探测并选出最佳链接"""

    def __init__(self, prober: LinkProber, max_workers: int = 3):
        self.prober = prober
        self.max_workers = max_workers

    def select_best(
        self,
        urls: List[Dict[str, str]],
        strategy: str = "fastest",
        timeout: float = 6.0,
    ) -> Dict:
        results = []
        if not urls:
            return {"best_url": None, "results": results, "reason": "no_urls"}

        # 并发探测
        with ThreadPoolExecutor(max_workers=self.max_workers) as exe:
            future_map = {
                exe.submit(self.prober.probe, u["url"], timeout): u for u in urls
            }
            for fut in as_completed(future_map):
                base = future_map[fut]
                try:
                    r = fut.result()
                except Exception as e:
                    r = {"url": base["url"], "reachable": False, "error": str(e)}
                r.update({"name": base.get("name", ""), "type": base.get("type", "")})
                results.append(r)

        # 过滤可达
        reachable = [r for r in results if r.get("reachable")]
        if not reachable:
            return {"best_url": None, "results": results, "reason": "no_reachable"}

        if strategy == "priority_first":
            # 按传入urls的顺序找到第一个 reachable
            order = {u["url"]: i for i, u in enumerate(urls)}
            reachable.sort(key=lambda r: order.get(r.get("url"), 1e9))
            best = reachable[0]
        else:
            # fastest：优先吞吐（降序），其次RTT（升序）
            def sort_key(r):
                tput = r.get("tput_kbps") or 0.0
                rtt = r.get("rtt") or 1e9
                return (-tput, rtt)

            reachable.sort(key=sort_key)
            best = reachable[0]

        return {
            "best_url": best.get("original_url") or best.get("url"),
            "results": results,
            "reason": "ok",
        }


class NetworkManager:
    def __init__(self):
        self.source_manager = SourceManager()
        self.version_info = None  # 存储版本信息
        self.prober = LinkProber()
        self.selector = MultiSourceSelector(self.prober)

        # 创建实例时自动获取远程文件
        self.fetch_remote_files()

    def fetch_from_source(self, url, timeout=5):
        """从单个源获取数据"""
        logging.debug(f"网络工具GET请求 - URL: {url}")
        try:
            response = requests.get(
                url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"}
            )
            if response.status_code == 200:
                return {
                    "text": response.text,  # 只保留实际使用的字段
                    "success": True,
                    "status_code": response.status_code,
                }
        except Exception:
            pass
        return {"success": False}

    def save_to_local(self, content, file_path):
        """保存内容到本地文件"""
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except Exception as e:
            logging.error(f"保存文件失败: {str(e)}")
            return False

    def fetch_remote_files(self, source=None):
        """从远程获取version.json和changelog.txt"""
        try:
            source_priority = self.source_manager.normalize_source_input(source)
            version_path = "updates/version.json"
            changelog_path = "updates/changelog.txt"

            # 获取version.json
            version_urls = self.source_manager.get_source_urls(
                version_path, source_priority
            )
            for source_info in version_urls:
                result = self.fetch_from_source(source_info["url"], timeout=10)
                if result and result["success"]:
                    self.version_info = json.loads(result["text"])  # 解析并存储版本信息
                    self.save_to_local(result["text"], "updates/version.json")
                    break

            # 获取changelog.txt
            changelog_urls = self.source_manager.get_source_urls(
                changelog_path, source_priority
            )
            for source_info in changelog_urls:
                result = self.fetch_from_source(source_info["url"], timeout=10)
                if result and result["success"]:
                    self.save_to_local(result["text"], "updates/changelog.txt")
                    break

            return True
        except Exception as e:
            logging.error(f"获取远程文件失败: {str(e)}")
            return False

    def _build_candidate_download_urls(
        self,
        package_name: str,
        tag: str = "latest",
        source_priority: Optional[List[str]] = None,
    ) -> List[Dict[str, str]]:
        # 合并 custom_sources 与 平台源
        custom_sources = (
            (self.version_info or {}).get("sources", {}).get("download_url", {})
        )
        urls = []

        # 1) 自定义源（直接URL或模板）
        for name, tpl in custom_sources.items():
            if not isinstance(tpl, str):
                continue
            url = tpl.replace("{tag}", tag).replace("{filename}", package_name)
            if url.startswith("http"):
                urls.append({"name": name, "url": url, "type": "custom"})

        # 2) 平台源
        urls += self.source_manager.get_release_urls(
            filename=package_name,
            tag=tag,
            source_priority=source_priority or self.source_manager.default_priority,
            custom_sources=None,
        )

        # 去重
        seen = set()
        deduped = []
        for u in urls:
            if u["url"] in seen:
                continue
            seen.add(u["url"])
            deduped.append(u)
        return deduped

    def open_best_download_in_browser(
        self,
        package_name: str = "BBH3ScanLaunch_Setup.exe",
        tag: str = "latest",
        source_priority: Optional[List[str]] = None,
        strategy: str = "fastest",
    ) -> bool:
        """探测多个源，选择最佳URL并用默认浏览器打开"""
        # 确保有版本信息（以获取自定义源）
        if not self.version_info:
            if not self.fetch_remote_files():
                logging.error("无法获取版本信息，放弃自动选择下载源")
                return False

        candidates = self._build_candidate_download_urls(
            package_name=package_name, tag=tag, source_priority=source_priority
        )
        if not candidates:
            logging.error("没有可用的候选下载链接")
            return False

        sel = self.selector.select_best(candidates, strategy=strategy)
        best = sel.get("best_url")
        if not best:
            logging.error("所有下载源均不可达，将尝试打开项目主页")
            # 兜底到仓库Release页
            try:
                webbrowser.open(
                    "https://github.com/LoveElysia1314/BBH3ScanLaunch/releases"
                )
            except Exception:
                return False
            return False

        # 获取最终 URL 用于浏览器打开（处理重定向）
        final_url = best
        try:
            resp = requests.head(
                best,
                timeout=5,
                allow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if resp.status_code == 200:
                final_url = resp.url
        except Exception:
            pass  # 如果获取失败，使用原始 URL

        logging.info(f"选择最佳下载源: {best}")
        try:
            webbrowser.open(final_url)
            return True
        except Exception as e:
            logging.error(f"无法打开浏览器: {str(e)}")
            return False


# 全局网络管理实例
network_manager = NetworkManager()
