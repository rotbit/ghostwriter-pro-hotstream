"""
API 使用示例
"""

import asyncio
import aiohttp
import json
from typing import Dict, Any


class HotStreamAPIClient:
    """HotStream API 客户端"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self.session: aiohttp.ClientSession = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """发送 HTTP 请求"""
        url = f"{self.base_url}{endpoint}"
        
        async with self.session.request(method, url, **kwargs) as response:
            result = await response.json()
            
            if response.status >= 400:
                raise Exception(f"API 请求失败: {result.get('detail', 'Unknown error')}")
            
            return result
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return await self._request("GET", "/health")
    
    async def search(self, platform: str, keywords: list, limit: int = 100, **options) -> Dict[str, Any]:
        """立即搜索"""
        data = {
            "platform": platform,
            "keywords": keywords,
            "limit": limit,
            **options
        }
        return await self._request("POST", "/search", json=data)
    
    async def list_platforms(self) -> Dict[str, Any]:
        """获取支持的平台"""
        return await self._request("GET", "/platforms")
    
    async def create_task(self, task_id: str, name: str, platform: str, keywords: list, 
                         schedule: str = None, **options) -> Dict[str, Any]:
        """创建任务"""
        data = {
            "task_id": task_id,
            "name": name,
            "platform": platform,
            "keywords": keywords,
            "schedule": schedule,
            **options
        }
        return await self._request("POST", "/tasks", json=data)
    
    async def list_tasks(self) -> Dict[str, Any]:
        """获取任务列表"""
        return await self._request("GET", "/tasks")
    
    async def get_task(self, task_id: str) -> Dict[str, Any]:
        """获取任务详情"""
        return await self._request("GET", f"/tasks/{task_id}")
    
    async def execute_task(self, task_id: str) -> Dict[str, Any]:
        """立即执行任务"""
        return await self._request("POST", f"/tasks/{task_id}/execute")
    
    async def delete_task(self, task_id: str) -> Dict[str, Any]:
        """删除任务"""
        return await self._request("DELETE", f"/tasks/{task_id}")
    
    async def get_status(self) -> Dict[str, Any]:
        """获取框架状态"""
        return await self._request("GET", "/status")


async def api_examples():
    """API 使用示例"""
    
    async with HotStreamAPIClient() as client:
        print("=== HotStream API 使用示例 ===\n")
        
        try:
            # 1. 健康检查
            print("1. 健康检查")
            health = await client.health_check()
            print(f"服务状态: {health['message']}")
            print(f"数据: {json.dumps(health['data'], indent=2, ensure_ascii=False)}\n")
            
            # 2. 获取支持的平台
            print("2. 获取支持的平台")
            platforms = await client.list_platforms()
            print(f"支持的平台: {platforms['data']}\n")
            
            # 3. 立即搜索
            print("3. 立即搜索")
            search_result = await client.search(
                platform="twitter",
                keywords=["AI", "机器学习"],
                limit=5
            )
            print(f"搜索结果: {search_result['message']}")
            if search_result['data']:
                print("前3条结果:")
                for i, item in enumerate(search_result['data'][:3]):
                    print(f"  {i+1}. {item['content'][:100]}...")
            print()
            
            # 4. 创建定时任务
            print("4. 创建定时任务")
            task_result = await client.create_task(
                task_id="api_test_task",
                name="API 测试任务",
                platform="twitter",
                keywords=["技术", "编程"],
                schedule="0 */2 * * *",  # 每2小时执行一次
                limit=50
            )
            print(f"任务创建: {task_result['message']}\n")
            
            # 5. 获取任务列表
            print("5. 获取任务列表")
            tasks = await client.list_tasks()
            print(f"任务总数: {len(tasks['data'])}")
            for task in tasks['data']:
                print(f"  - {task['task_id']}: {task['name']} ({task['status']})")
            print()
            
            # 6. 立即执行任务
            print("6. 立即执行任务")
            execute_result = await client.execute_task("api_test_task")
            print(f"任务执行: {execute_result['message']}\n")
            
            # 7. 获取框架状态
            print("7. 获取框架状态")
            status = await client.get_status()
            print(f"框架状态: {json.dumps(status['data'], indent=2, ensure_ascii=False)}\n")
            
            # 8. 清理测试任务
            print("8. 清理测试任务")
            delete_result = await client.delete_task("api_test_task")
            print(f"任务删除: {delete_result['message']}")
            
        except Exception as e:
            print(f"API 调用失败: {e}")


async def batch_search_example():
    """批量搜索示例"""
    
    async with HotStreamAPIClient() as client:
        print("\n=== 批量搜索示例 ===\n")
        
        platforms = ["twitter"]  # 可以添加更多平台
        keywords_sets = [
            ["AI", "人工智能"],
            ["机器学习", "深度学习"],
            ["Python", "编程"]
        ]
        
        for platform in platforms:
            for keywords in keywords_sets:
                try:
                    print(f"搜索 {platform} 平台，关键字: {keywords}")
                    result = await client.search(
                        platform=platform,
                        keywords=keywords,
                        limit=10
                    )
                    
                    print(f"  结果: {result['message']}")
                    if result['data']:
                        print(f"  示例内容: {result['data'][0]['content'][:80]}...")
                    print()
                    
                    # 避免请求过于频繁
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    print(f"  搜索失败: {e}\n")


if __name__ == "__main__":
    print("请确保 HotStream 服务正在运行:")
    print("python -m hotstream.cli start --daemon")
    print()
    
    # 运行基本示例
    asyncio.run(api_examples())
    
    # 运行批量搜索示例
    asyncio.run(batch_search_example())