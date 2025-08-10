#!/usr/bin/env python3
"""
主调度程序 - 定时执行excellentnumberstack和numberbarntask任务
"""
import time
import schedule
import logging
from datetime import datetime
import sys
import os
import importlib.util

# 添加模块路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'excellentnumberstask'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'numberbarntask'))

try:
    from excellentnumberstask.excellentnumberstask import AreaCodeNumbersHarvester
    from numberbarntask.numberbarntask import NumberbarnNumberExtractor
except ImportError:
    # 直接导入模块
    
    # 加载excellentnumberstask
    spec1 = importlib.util.spec_from_file_location(
        "excellentnumberstask", 
        os.path.join(os.path.dirname(__file__), "excellentnumberstask", "excellentnumberstask.py")
    )
    excellentnumbers_module = importlib.util.module_from_spec(spec1)
    spec1.loader.exec_module(excellentnumbers_module)
    AreaCodeNumbersHarvester = excellentnumbers_module.AreaCodeNumbersHarvester
    
    # 加载numberbarntask
    spec2 = importlib.util.spec_from_file_location(
        "numberbarntask", 
        os.path.join(os.path.dirname(__file__), "numberbarntask", "numberbarntask.py")
    )
    numberbarn_module = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(numberbarn_module)
    NumberbarnNumberExtractor = numberbarn_module.NumberbarnNumberExtractor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('numharvest_scheduler.log'),
        logging.StreamHandler()
    ]
)

class NumberHarvestScheduler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.excellentnumbers_harvester = None
        self.numberbarn_extractor = None
        self.is_running = False
        
        # 初始化任务实例
        self._init_harvesters()
        
    def _init_harvesters(self):
        """初始化爬虫实例"""
        try:
            # 初始化excellentnumbers爬虫
            self.excellentnumbers_harvester = AreaCodeNumbersHarvester(
                mongo_host="43.159.58.235",
                mongo_user="extra_numbers", 
                mongo_password="RsBWd3hTAZeR7kC4",
                mongo_port=27017,
                mongo_db="extra_numbers",
                mongo_collection="numbers",
                headless=True,
                min_delay=1.2,
                max_delay=3.5,
                long_pause_every=20,
                long_pause_range=(8.0, 15.0),
                retries=2,
                retry_backoff_base=1.8,
                retry_jitter=(0.3, 0.9),
            )
            
            # 初始化numberbarn爬虫
            self.numberbarn_extractor = NumberbarnNumberExtractor(
                mongo_host="43.159.58.235",
                mongo_password="RsBWd3hTAZeR7kC4",
                mongo_db="extra_numbers"
            )
            
            self.logger.info("爬虫实例初始化完成")
            
        except Exception as e:
            self.logger.error(f"初始化爬虫实例失败: {e}")
            
    def run_excellentnumbers_task(self):
        """执行excellentnumbers任务"""
        if self.is_running:
            self.logger.warning("有任务正在运行，跳过本次excellentnumbers任务")
            return
            
        self.is_running = True
        start_time = datetime.now()
        self.logger.info("开始执行excellentnumbers任务")
        
        try:
            if self.excellentnumbers_harvester:
                result = self.excellentnumbers_harvester.run(
                    index_path_or_dir=".",
                    limit=None
                )
                
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                self.logger.info(f"excellentnumbers任务完成，耗时: {duration:.2f}秒")
                self.logger.info(f"任务结果: {result}")
            else:
                self.logger.error("excellentnumbers_harvester未初始化")
                
        except Exception as e:
            self.logger.error(f"执行excellentnumbers任务时出错: {e}")
        finally:
            self.is_running = False
            
    def run_numberbarn_task(self):
        """执行numberbarn任务"""
        if self.is_running:
            self.logger.warning("有任务正在运行，跳过本次numberbarn任务")
            return
            
        self.is_running = True
        start_time = datetime.now()
        self.logger.info("开始执行numberbarn任务")
        
        try:
            if self.numberbarn_extractor:
                numbers = self.numberbarn_extractor.run()
                
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                self.logger.info(f"numberbarn任务完成，耗时: {duration:.2f}秒")
                self.logger.info(f"提取到 {len(numbers)} 个号码")
            else:
                self.logger.error("numberbarn_extractor未初始化")
                
        except Exception as e:
            self.logger.error(f"执行numberbarn任务时出错: {e}")
        finally:
            self.is_running = False
            
    def setup_schedule(self):
        """设置定时任务调度"""
        # excellentnumbers任务：每天凌晨2点执行
        schedule.every().day.at("02:00").do(self.run_excellentnumbers_task)
        
        # numberbarn任务：每天早上6点执行
        schedule.every().day.at("06:00").do(self.run_numberbarn_task)
        
        # 也可以设置更频繁的执行周期，例如：
        # schedule.every(6).hours.do(self.run_excellentnumbers_task)
        # schedule.every(8).hours.do(self.run_numberbarn_task)
        
        self.logger.info("定时任务调度设置完成")
        self.logger.info("excellentnumbers任务：每天凌晨2点执行")
        self.logger.info("numberbarn任务：每天早上6点执行")
        
    def run_scheduler(self):
        """运行调度器主循环"""
        self.setup_schedule()
        self.logger.info("数字收获调度器启动")
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # 每分钟检查一次
        except KeyboardInterrupt:
            self.logger.info("接收到中断信号，正在停止调度器...")
        except Exception as e:
            self.logger.error(f"调度器运行错误: {e}")
        finally:
            self.logger.info("调度器已停止")
            
    def run_once_each(self):
        """立即执行一次两个任务（用于测试）"""
        self.logger.info("开始执行一次性任务测试")
        
        # 先执行excellentnumbers任务
        self.run_excellentnumbers_task()
        
        # 等待5分钟后执行numberbarn任务
        self.logger.info("等待5分钟后执行numberbarn任务...")
        time.sleep(300)
        
        # 执行numberbarn任务
        self.run_numberbarn_task()
        
        self.logger.info("一次性任务执行完成")


def main():
    """主函数"""
    scheduler = NumberHarvestScheduler()
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] == "--test":
            # 测试模式：立即执行一次每个任务
            scheduler.run_once_each()
        elif sys.argv[1] == "--excellentnumbers":
            # 只执行excellentnumbers任务
            scheduler.run_excellentnumbers_task()
        elif sys.argv[1] == "--numberbarn":
            # 只执行numberbarn任务
            scheduler.run_numberbarn_task()
        else:
            print("使用方法:")
            print("  python main.py                    # 启动定时调度器")
            print("  python main.py --test             # 测试模式，立即执行一次每个任务")
            print("  python main.py --excellentnumbers # 只执行excellentnumbers任务")
            print("  python main.py --numberbarn       # 只执行numberbarn任务")
    else:
        # 正常模式：启动定时调度器
        scheduler.run_scheduler()


if __name__ == "__main__":
    main()