import asyncio
import json
import time
from typing import Any, Dict, List
from playwright.async_api import async_playwright
from base_scraper import BaseScraper

class ExcellentnumbersScraper(BaseScraper):
    """Excellentnumbers网站的全球区号爬虫"""
    
    def __init__(self, base_url: str = "https://excellentnumbers.com/"):
        super().__init__(base_url, "excellentnumbers_data.json")
    
    def _default_filename(self) -> str:
        """返回默认的输出文件名"""
        return "excellentnumbers_data.json"
    
    async def fetch_data(self) -> List[Dict[str, Any]]:
        """
        数据获取 - 使用Playwright从网站获取所有相关链接
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                print(f"正在访问: {self.base_url}")
                await page.goto(self.base_url, wait_until="networkidle")
                await page.wait_for_timeout(2000)
                
                # 获取页面上所有包含categories的链接
                links = await page.evaluate("""
                    () => {
                        const links = [];
                        const anchors = document.querySelectorAll('a');
                        
                        anchors.forEach(anchor => {
                            const href = anchor.getAttribute('href');
                            const text = anchor.textContent.trim();
                            
                            if (href && href.includes('/categories/') && text) {
                                links.push({
                                    text: text,
                                    href: href,
                                    fullUrl: href.startsWith('http') ? href : 'https://excellentnumbers.com' + href
                                });
                            }
                        });
                        
                        return links;
                    }
                """)
                
                return links
                
            except Exception as e:
                print(f"获取数据时出错: {e}")
                raise
            finally:
                await browser.close()
    
    def parse_data(self, raw_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        数据解析 - 将原始链接数据解析成地区和区号的结构化数据
        """
        regions_data = {}
        area_codes_data = {}
        
        print(f"正在解析 {len(raw_data)} 个链接...")
        
        # 分类处理链接
        region_links = []
        area_code_links = []
        
        for link in raw_data:
            text = link['text']
            href = link['href']
            url_parts = href.split('/')
            
            if len(url_parts) >= 3:
                # 检查是否是区号链接 (最后一部分是数字)
                if url_parts[-1].isdigit():
                    area_code = url_parts[-1]
                    region_name = url_parts[-2].replace('%20', ' ')
                    
                    # 处理所有地区，不限制于美国州
                    area_code_links.append({
                        'area_code': area_code,
                        'region_name': region_name,
                        'url': href
                    })
                
                else:
                    # 这是一个地区链接
                    region_links.append({
                        'region_name': text,
                        'url': href
                    })
        
        print(f"解析得到 {len(region_links)} 个地区链接，{len(area_code_links)} 个区号链接")
        
        # 处理地区链接
        for region_link in region_links:
            region_name = region_link['region_name']
            if region_name not in regions_data:
                regions_data[region_name] = {
                    'name': region_name,
                    'url': region_link['url'],
                    'area_codes': []
                }
        
        # 处理区号链接
        for area_link in area_code_links:
            region_name = area_link['region_name']
            area_code = area_link['area_code']
            url = area_link['url']
            
            # 确保地区存在
            if region_name not in regions_data:
                regions_data[region_name] = {
                    'name': region_name,
                    'url': f"/categories/{region_name}",
                    'area_codes': []
                }
            
            # 添加区号到地区
            area_code_info = {
                'code': area_code,
                'url': url
            }
            
            # 检查是否已存在
            existing_codes = [ac['code'] for ac in regions_data[region_name]['area_codes']]
            if area_code not in existing_codes:
                regions_data[region_name]['area_codes'].append(area_code_info)
            
            # 添加到区号字典
            area_codes_data[area_code] = {
                'code': area_code,
                'region': region_name,
                'url': url
            }
        
        return {
            'regions': regions_data,
            'area_codes': area_codes_data,
            'metadata': {
                'total_regions': len(regions_data),
                'total_area_codes': len(area_codes_data),
                'scrape_timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'source_url': self.base_url,
                'description': 'Global regions and Area Codes from excellentnumbers.com'
            }
        }
    
    def store_data(self, data: Dict[str, Any], filename: str = None) -> str:
        """
        数据存储 - 将解析后的数据保存为JSON文件
        """
        output_file = filename or self.output_filename
        
        # 格式化数据以便更好的展示
        formatted_data = {
            'regions': {},
            'area_codes': data['area_codes'],
            'summary': data['metadata']
        }
        
        # 按地区名排序并格式化地区数据
        for region_name in sorted(data['regions'].keys()):
            region_info = data['regions'][region_name]
            # 按区号排序
            sorted_area_codes = sorted(region_info['area_codes'], key=lambda x: x['code'])
            formatted_data['regions'][region_name] = {
                'name': region_name,
                'area_codes': sorted_area_codes,
                'total_area_codes': len(sorted_area_codes)
            }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(formatted_data, f, indent=2, ensure_ascii=False)
        
        print(f"数据已保存到: {output_file}")
        return output_file
    
    def print_summary(self):
        """打印数据摘要"""
        if not self.processed_data:
            print("没有可用的数据摘要")
            return
        
        metadata = self.processed_data.get('metadata', {})
        regions = self.processed_data.get('regions', {})
        area_codes = self.processed_data.get('area_codes', {})
        
        print(f"\n=== 抓取结果摘要 ===")
        print(f"数据源: {metadata.get('source_url', 'N/A')}")
        print(f"抓取时间: {metadata.get('scrape_timestamp', 'N/A')}")
        print(f"地区总数: {metadata.get('total_regions', 0)}")
        print(f"区号总数: {metadata.get('total_area_codes', 0)}")
        
        # 显示有区号的地区
        regions_with_codes = {k: v for k, v in regions.items() if v.get('area_codes')}
        if regions_with_codes:
            print(f"\n=== 各地区区号统计 (前20个) ===")
            for region_name, region_info in sorted(regions_with_codes.items())[:20]:
                area_codes_count = len(region_info.get('area_codes', []))
                print(f"  {region_name}: {area_codes_count} 个区号")
            
            if len(regions_with_codes) > 20:
                print(f"  ... 还有 {len(regions_with_codes) - 20} 个地区")
        
        # 显示区号示例
        if area_codes:
            print(f"\n=== 区号示例 (前10个) ===")
            for code, info in list(area_codes.items())[:10]:
                print(f"  {code} -> {info.get('region', 'N/A')}")

async def main():
    """主函数 - 演示如何使用爬虫"""
    scraper = ExcellentnumbersScraper()
    
    try:
        # 执行完整的抓取流程
        output_file = await scraper.execute()
        
        # 打印摘要
        scraper.print_summary()
        
        return output_file
        
    except Exception as e:
        print(f"抓取失败: {e}")
        return None

if __name__ == "__main__":
    asyncio.run(main())