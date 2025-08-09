import asyncio
import json
import time
from typing import Any, Dict, List, Optional
from playwright.async_api import async_playwright
from base_scraper import BaseScraper
from pymongo import MongoClient
from datetime import datetime

class NumbersExtractor(BaseScraper):
    """从excellentnumbers.com提取号码数据的爬虫"""
    
    def __init__(self, data_file: str = "excellentnumbers_data.json", 
                 mongo_host: str = "43.159.58.235", 
                 mongo_password: str = "RsBWd3hTAZeR7kC4",
                 mongo_db: str = "extra_numbers"):
        super().__init__("https://excellentnumbers.com", "extracted_numbers.json")
        self.data_file = data_file
        self.urls_to_process = []
        
        # MongoDB配置
        self.mongo_host = mongo_host
        self.mongo_password = mongo_password
        self.mongo_db = mongo_db
        self.mongo_client = None
        self.db = None
        self.collection = None
        
        # 初始化MongoDB连接
        self.init_mongodb()
    
    def _default_filename(self) -> str:
        """返回默认的输出文件名"""
        return "extracted_numbers.json"
    
    def init_mongodb(self):
        """初始化MongoDB连接"""
        try:
            # 构建连接字符串，假设使用默认用户名admin
            connection_string = f"mongodb://extra_numbers:{self.mongo_password}@{self.mongo_host}:27017/{self.mongo_db}?authSource=extra_numbers"
            
            self.mongo_client = MongoClient(connection_string)
            self.db = self.mongo_client[self.mongo_db]
            self.collection = self.db['extra_numbers']
            
            # 测试连接
            self.mongo_client.admin.command('ping')
            print(f"成功连接到MongoDB数据库: {self.mongo_db}")
            
            # 创建索引提高查询效率
            self.collection.create_index("number", unique=True)
            self.collection.create_index([("region", 1), ("area_code", 1)])
            
        except Exception as e:
            print(f"MongoDB连接失败: {e}")
            self.mongo_client = None
    
    def save_numbers_to_mongodb(self, numbers: List[Dict]) -> bool:
        """将号码列表保存到MongoDB，每个号码一条记录"""
        if not self.mongo_client or not numbers:
            return False
        
        try:
            # 准备文档列表
            documents = []
            current_time = datetime.utcnow()
            
            for number_data in numbers:
                doc = {
                    'number': number_data.get('number', ''),
                    'price': number_data.get('price', ''),
                    'region': number_data.get('region', ''),
                    'area_code': number_data.get('area_code', ''),
                    'page': number_data.get('page', 1),
                    'source_url': number_data.get('source_url', ''),
                    'created_at': current_time,
                    'updated_at': current_time
                }
                documents.append(doc)
            
            # 批量插入，忽略重复记录
            if documents:
                try:
                    result = self.collection.insert_many(documents, ordered=False)
                    print(f"  MongoDB: 成功插入 {len(result.inserted_ids)} 条记录")
                    return True
                except Exception as e:
                    # 处理重复键错误
                    if 'duplicate key error' in str(e).lower() or 'E11000' in str(e):
                        # 逐条插入以处理重复记录
                        inserted_count = 0
                        for doc in documents:
                            try:
                                self.collection.insert_one(doc)
                                inserted_count += 1
                            except Exception:
                                # 记录已存在，更新时间戳
                                try:
                                    self.collection.update_one(
                                        {'number': doc['number']},
                                        {'$set': {'updated_at': current_time}}
                                    )
                                except Exception:
                                    pass
                        print(f"  MongoDB: 插入 {inserted_count} 条新记录，跳过重复记录")
                        return True
                    else:
                        raise e
                        
        except Exception as e:
            print(f"  MongoDB保存失败: {e}")
            return False
        
        return False
    
    def close_mongodb(self):
        """关闭MongoDB连接"""
        if self.mongo_client:
            self.mongo_client.close()
            print("MongoDB连接已关闭")
    
    def __del__(self):
        """析构函数，确保关闭MongoDB连接"""
        self.close_mongodb()
    
    def load_urls_from_data(self) -> List[str]:
        """从excellentnumbers_data.json读取所有URL"""
        try:
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            urls = []
            regions = data.get('regions', {})
            
            for region_name, region_info in regions.items():
                area_codes = region_info.get('area_codes', [])
                for area_code_info in area_codes:
                    base_url = area_code_info.get('url', '')
                    if base_url:
                        # 添加排序参数，从newest开始
                        url_with_sort = f"{base_url}?sort=newest&sortcode="
                        urls.append({
                            'region': region_name,
                            'area_code': area_code_info.get('code', ''),
                            'url': url_with_sort
                        })
            
            print(f"从{self.data_file}加载了{len(urls)}个URL")
            return urls
            
        except Exception as e:
            print(f"加载URL数据失败: {e}")
            return []
    
    async def extract_numbers_from_page(self, page, url_info: Dict, page_num: int = 1) -> List[Dict]:
        """从单页提取号码数据"""
        numbers = []
        
        try:
            # 构建带页码的URL
            base_url = url_info['url']
            if page_num > 1:
                paginated_url = f"{base_url}&page={page_num}"
            else:
                paginated_url = base_url
            
            print(f"正在处理: {url_info['region']} - {url_info['area_code']} - 第{page_num}页")
            await page.goto(paginated_url, wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(2000)
            
            # 提取号码数据
            page_numbers = await page.evaluate("""
                () => {
                    const numbers = [];
                    
                    // 查找包含号码信息的元素
                    const numberElements = document.querySelectorAll('.number-item, .phone-number, .listing-item, [data-phone], .number-card');
                    
                    if (numberElements.length === 0) {
                        // 如果没有找到标准选择器，尝试其他常见模式
                        const allElements = document.querySelectorAll('*');
                        allElements.forEach(el => {
                            const text = el.textContent || '';
                            // 查找电话号码模式 (xxx) xxx-xxxx
                            const phonePattern = /\(\d{3}\)\s*\d{3}[-.\s]?\d{4}/g;
                            const matches = text.match(phonePattern);
                            if (matches) {
                                matches.forEach(match => {
                                    // 查找价格信息
                                    const priceEl = el.querySelector('[data-price], .price, [class*="price"]') || 
                                                  el.parentElement?.querySelector('[data-price], .price, [class*="price"]') ||
                                                  el.closest('[data-price], .price, [class*="price"]');
                                    const priceText = priceEl?.textContent || '';
                                    const priceMatch = priceText.match(/\$[\d,]+\.?\d*/);
                                    
                                    if (!numbers.some(n => n.number === match.trim())) {
                                        numbers.push({
                                            number: match.trim(),
                                            price: priceMatch ? priceMatch[0] : '',
                                            element_html: el.outerHTML.substring(0, 200)
                                        });
                                    }
                                });
                            }
                        });
                    } else {
                        numberElements.forEach(el => {
                            const numberText = el.textContent || '';
                            const phonePattern = /\(\d{3}\)\s*\d{3}[-.\s]?\d{4}/g;
                            const phoneMatch = numberText.match(phonePattern);
                            
                            if (phoneMatch) {
                                const priceMatch = numberText.match(/\$[\d,]+\.?\d*/);
                                
                                numbers.push({
                                    number: phoneMatch[0].trim(),
                                    price: priceMatch ? priceMatch[0] : '',
                                    raw_text: numberText.trim()
                                });
                            }
                        });
                    }
                    
                    return numbers;
                }
            """)
            
            # 添加区域和区号信息
            for number in page_numbers:
                number.update({
                    'region': url_info['region'],
                    'area_code': url_info['area_code'],
                    'page': page_num,
                    'source_url': paginated_url
                })
                numbers.append(number)
            
            # 立即保存到MongoDB
            if numbers:
                self.save_numbers_to_mongodb(numbers)
            
            # 检查是否有下一页
            has_next_page = await page.evaluate("""
                () => {
                    // 查找包含"Next"文本的链接
                    const allLinks = document.querySelectorAll('a[href*="page"]');
                    let nextButton = null;
                    
                    for (let link of allLinks) {
                        const text = link.textContent.toLowerCase().trim();
                        if (text.includes('next') || text === '»' || text === '>') {
                            nextButton = link;
                            break;
                        }
                    }
                    
                    // 如果找到下一页按钮且不是禁用状态
                    if (nextButton && !nextButton.classList.contains('disabled') && !nextButton.classList.contains('inactive')) {
                        return true;
                    }
                    
                    // 检查页码链接
                    const pageLinks = document.querySelectorAll('a[href*="page="]');
                    const currentPageNum = new URL(window.location.href).searchParams.get('page') || '1';
                    const currentPage = parseInt(currentPageNum);
                    
                    // 查找更大的页码
                    for (let link of pageLinks) {
                        const linkPageMatch = link.href.match(/page=(\d+)/);
                        if (linkPageMatch) {
                            const linkPage = parseInt(linkPageMatch[1]);
                            if (linkPage > currentPage) {
                                return true;
                            }
                        }
                    }
                    
                    return false;
                }
            """)
            
            return numbers, has_next_page
            
        except Exception as e:
            print(f"提取页面数据失败 {paginated_url}: {e}")
            return [], False
    
    async def fetch_data(self) -> List[Dict[str, Any]]:
        """数据获取 - 从所有URL提取号码数据"""
        # 先加载URL列表
        url_list = self.load_urls_from_data()
        if not url_list:
            print("没有找到可处理的URL")
            return []
        
        all_numbers = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                for i, url_info in enumerate(url_list):
                    print(f"\n处理进度: {i+1}/{len(url_list)} - {url_info['region']} {url_info['area_code']}")
                    
                    # 从第一页开始提取
                    page_num = 1
                    has_next_page = True
                    
                    while has_next_page and page_num <= 50:  # 限制最大页数防止无限循环
                        try:
                            numbers, has_next_page = await self.extract_numbers_from_page(page, url_info, page_num)
                            
                            if numbers:
                                all_numbers.extend(numbers)
                                print(f"  第{page_num}页: 提取到{len(numbers)}个号码")
                            else:
                                print(f"  第{page_num}页: 没有找到号码")
                                break
                            
                            page_num += 1
                            
                            # 添加延迟避免被限制
                            await page.wait_for_timeout(1000)
                            
                        except Exception as e:
                            print(f"  处理第{page_num}页时出错: {e}")
                            break
                    
                    print(f"  完成 {url_info['region']} {url_info['area_code']}: 共{page_num-1}页，{len([n for n in all_numbers if n['region'] == url_info['region'] and n['area_code'] == url_info['area_code']])}个号码")
                    
                    # 每处理几个URL就暂停一下
                    if i % 5 == 4:
                        print(f"已处理{i+1}个区域，暂停3秒...")
                        await page.wait_for_timeout(3000)
                        
            finally:
                await browser.close()
        
        return all_numbers
    
    def parse_data(self, raw_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """数据解析 - 整理和统计号码数据"""
        if not raw_data:
            return {
                'numbers': [],
                'summary': {
                    'total_numbers': 0,
                    'regions': 0,
                    'area_codes': 0,
                    'avg_price': 0
                }
            }
        
        # 去重处理
        unique_numbers = {}
        for item in raw_data:
            number = item.get('number', '').strip()
            if number and number not in unique_numbers:
                unique_numbers[number] = item
        
        numbers_list = list(unique_numbers.values())
        
        # 统计信息
        regions = set()
        area_codes = set()
        prices = []
        
        for item in numbers_list:
            if item.get('region'):
                regions.add(item['region'])
            if item.get('area_code'):
                area_codes.add(item['area_code'])
            
            # 提取价格数字
            price_str = item.get('price', '').replace('$', '').replace(',', '')
            try:
                if price_str:
                    prices.append(float(price_str))
            except ValueError:
                pass
        
        avg_price = sum(prices) / len(prices) if prices else 0
        
        return {
            'numbers': numbers_list,
            'summary': {
                'total_numbers': len(numbers_list),
                'regions': len(regions),
                'area_codes': len(area_codes),
                'avg_price': round(avg_price, 2),
                'price_range': {
                    'min': min(prices) if prices else 0,
                    'max': max(prices) if prices else 0
                },
                'scrape_timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'regions_list': sorted(list(regions)),
                'area_codes_list': sorted(list(area_codes))
            }
        }
    
    def store_data(self, data: Dict[str, Any], filename: str = None) -> str:
        """数据存储 - 保存到JSON文件"""
        output_file = filename or self.output_filename
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"数据已保存到: {output_file}")
        
        # 打印摘要
        summary = data.get('summary', {})
        print(f"\n=== 提取结果摘要 ===")
        print(f"总号码数: {summary.get('total_numbers', 0)}")
        print(f"涉及地区: {summary.get('regions', 0)}")
        print(f"涉及区号: {summary.get('area_codes', 0)}")
        print(f"平均价格: ${summary.get('avg_price', 0)}")
        if summary.get('price_range'):
            print(f"价格范围: ${summary['price_range']['min']} - ${summary['price_range']['max']}")
        
        return output_file

async def main():
    """主函数 - 演示如何使用号码提取器"""
    extractor = NumbersExtractor()
    
    try:
        # 执行完整的提取流程
        output_file = await extractor.execute()
        return output_file
        
    except Exception as e:
        print(f"提取失败: {e}")
        return None
    finally:
        # 确保关闭MongoDB连接
        extractor.close_mongodb()

if __name__ == "__main__":
    asyncio.run(main())