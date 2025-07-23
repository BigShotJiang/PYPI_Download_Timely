import requests
import json
import os
import time
from datetime import datetime, timedelta
from urllib.parse import urljoin
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PyPICrawler:
    def __init__(self, download_dir="pypi_packages"):
        self.download_dir = download_dir
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'PyPI-Crawler/1.0 (Educational Purpose)'
        })
        
        # 创建下载目录
        os.makedirs(download_dir, exist_ok=True)
    
    def get_package_info(self, package_name):
        """获取包的详细信息"""
        url = f"https://pypi.org/pypi/{package_name}/json"
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"获取包 {package_name} 信息失败: {e}")
            return None
    
    def is_updated_since_july_2025(self, package_info):
        """检查包是否在2025年7月后更新"""
        try:
            # 获取最新版本的上传时间
            latest_version = package_info['info']['version']
            releases = package_info['releases']
            
            if latest_version in releases:
                release_files = releases[latest_version]
                if release_files:
                    # 获取最新文件的上传时间
                    upload_time = release_files[0]['upload_time_iso_8601']
                    upload_date = datetime.fromisoformat(upload_time.replace('Z', '+00:00'))
                    cutoff_date = datetime(2025, 7, 1, tzinfo=upload_date.tzinfo)
                    return upload_date >= cutoff_date
        except (KeyError, ValueError, IndexError) as e:
            logger.warning(f"解析时间失败: {e}")
        return False
    
    def download_package(self, package_name, package_info):
        """下载包的tar.gz文件"""
        try:
            latest_version = package_info['info']['version']
            releases = package_info['releases'][latest_version]
            
            # 寻找tar.gz文件
            tar_gz_file = None
            for file_info in releases:
                if file_info['filename'].endswith('.tar.gz'):
                    tar_gz_file = file_info
                    break
            
            if not tar_gz_file:
                # 如果没有tar.gz，尝试下载wheel文件
                for file_info in releases:
                    if file_info['filename'].endswith('.whl'):
                        tar_gz_file = file_info
                        break
            
            if tar_gz_file:
                download_url = tar_gz_file['url']
                filename = tar_gz_file['filename']
                file_path = os.path.join(self.download_dir, filename)
                
                # 检查文件是否已存在
                if os.path.exists(file_path):
                    logger.info(f"文件已存在，跳过: {filename}")
                    return True
                
                logger.info(f"下载: {filename}")
                response = self.session.get(download_url, timeout=30)
                response.raise_for_status()
                
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                
                logger.info(f"下载完成: {filename}")
                return True
            else:
                logger.warning(f"未找到可下载的文件: {package_name}")
                return False
                
        except Exception as e:
            logger.error(f"下载包 {package_name} 失败: {e}")
            return False
    
    def get_packages_from_search(self, query="", classifier="", page_limit=50):
        """从PyPI搜索页面获取包列表"""
        packages = []
        
        # 方法1: 使用PyPI的搜索API
        for page in range(1, page_limit + 1):
            url = f"https://pypi.org/search/"
            params = {
                'q': query,
                'c': classifier,
                'page': page
            }
            
            try:
                response = self.session.get(url, params=params, timeout=10)
                response.raise_for_status()
                
                # 这里需要解析HTML来获取包名
                # 为了简化，我们使用另一种方法
                break
                
            except requests.RequestException as e:
                logger.error(f"搜索页面 {page} 失败: {e}")
                break
        
        return packages
    
    def get_recent_packages_from_rss(self):
        """从PyPI的RSS源获取最近更新的包"""
        packages = []
        try:
            # PyPI的最近更新RSS
            rss_url = "https://pypi.org/rss/updates.xml"
            response = self.session.get(rss_url, timeout=10)
            response.raise_for_status()
            
            # 简单的XML解析来获取包名
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.content)
            
            for item in root.findall('.//item'):
                title = item.find('title')
                if title is not None:
                    # 标题格式通常是 "package-name version"
                    package_name = title.text.split()[0]
                    if package_name not in packages:
                        packages.append(package_name)
            
            logger.info(f"从RSS获取到 {len(packages)} 个包")
            return packages[:100]  # 限制数量
            
        except Exception as e:
            logger.error(f"获取RSS失败: {e}")
            return []
    
    def crawl_and_download(self, package_list=None):
        """主要的爬取和下载方法"""
        if package_list is None:
            # 获取最近更新的包列表
            package_list = self.get_recent_packages_from_rss()
        
        if not package_list:
            logger.error("未获取到包列表")
            return
        
        logger.info(f"开始处理 {len(package_list)} 个包")
        downloaded_count = 0
        
        for i, package_name in enumerate(package_list, 1):
            logger.info(f"处理进度: {i}/{len(package_list)} - {package_name}")
            
            # 获取包信息
            package_info = self.get_package_info(package_name)
            if not package_info:
                continue
            
            # 检查是否在2025年7月后更新
            if not self.is_updated_since_july_2025(package_info):
                logger.info(f"包 {package_name} 不符合时间条件，跳过")
                continue
            
            # 下载包
            if self.download_package(package_name, package_info):
                downloaded_count += 1
            
            # 添加延迟，避免请求过于频繁
            time.sleep(1)
        
        logger.info(f"下载完成！共下载 {downloaded_count} 个包")

# 使用示例
if __name__ == "__main__":
    crawler = PyPICrawler(download_dir="pypi_packages_2025_july")
    
    # 方法1: 下载RSS中的最近更新包
    crawler.crawl_and_download()
    
    # 方法2: 指定包列表下载
    # specific_packages = ["aws-cdk.cloud-assembly-schema", "aws-cdk.region-info"]
    # crawler.crawl_and_download(specific_packages)