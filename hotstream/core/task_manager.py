"""
MongoDB任务管理器
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection

from .interfaces import TaskManager, Task, TaskStatus


class MongoTaskManager(TaskManager):
    """MongoDB任务管理器"""
    
    def __init__(self, mongo_uri: str = "mongodb://localhost:27017", db_name: str = "hotstream"):
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None
        self.tasks_collection: Optional[AsyncIOMotorCollection] = None
        self.initialized = False
    
    async def initialize(self) -> bool:
        """初始化MongoDB连接"""
        try:
            # 如果已经初始化过，直接返回成功
            if self.initialized:
                return True
                
            self.client = AsyncIOMotorClient(self.mongo_uri)
            self.db = self.client[self.db_name]
            self.tasks_collection = self.db.tasks
            
            # 测试连接
            await self.client.admin.command('ping')
            
            # 创建索引（如果已存在会被忽略）
            try:
                await self.tasks_collection.create_index("task_id", unique=True)
                await self.tasks_collection.create_index("status")
                await self.tasks_collection.create_index("platform")
                await self.tasks_collection.create_index("created_at")
                await self.tasks_collection.create_index([("status", 1), ("created_at", 1)])
            except Exception as index_error:
                logger.warning(f"创建索引时出现警告: {index_error}")
            
            self.initialized = True
            logger.info(f"MongoDB任务管理器初始化成功: {self.mongo_uri}")
            return True
            
        except Exception as e:
            logger.error(f"MongoDB任务管理器初始化失败: {e}")
            return False
    
    async def get_pending_tasks(self, limit: int = 10, priority_only: bool = False) -> List[Task]:
        """获取待处理的任务"""
        if not self.initialized or self.tasks_collection is None:
            logger.error("任务管理器未初始化")
            return []
        
        try:
            # 构建查询条件
            query = {"status": TaskStatus.PENDING.value}
            
            # 如果只查询高优先级或立即执行的任务
            if priority_only:
                query["$or"] = [
                    {"priority": {"$lte": 3}},  # 高优先级 1-3
                    {"immediate": True}  # 立即执行
                ]
            
            # 排序：立即执行 > 优先级 > 创建时间
            sort_criteria = [
                ("immediate", -1),  # 立即执行的优先
                ("priority", 1),    # 优先级数字越小越优先
                ("created_at", 1)   # 创建时间早的优先
            ]
            
            cursor = self.tasks_collection.find(query).sort(sort_criteria).limit(limit)
            
            tasks = []
            async for doc in cursor:
                # 转换MongoDB文档为Task对象
                doc.pop('_id', None)  # 移除MongoDB的_id字段
                
                # 处理datetime字段
                for field in ['created_at', 'updated_at', 'started_at', 'completed_at', 'last_heartbeat']:
                    if field in doc and doc[field]:
                        if isinstance(doc[field], str):
                            try:
                                doc[field] = datetime.fromisoformat(doc[field].replace('Z', '+00:00'))
                            except:
                                doc[field] = None
                
                task = Task(**doc)
                tasks.append(task)
            
            if priority_only and tasks:
                logger.info(f"获取到 {len(tasks)} 个高优先级/立即执行任务")
            else:
                logger.info(f"获取到 {len(tasks)} 个待处理任务")
            
            return tasks
            
        except Exception as e:
            logger.error(f"获取待处理任务失败: {e}")
            return []
    
    async def update_task_status(self, task_id: str, status: int, **kwargs) -> bool:
        """更新任务状态"""
        if not self.initialized or self.tasks_collection is None:
            logger.error("任务管理器未初始化")
            return False
        
        try:
            update_data = {
                "status": status,
                "updated_at": datetime.utcnow()
            }
            
            # 根据状态设置特定字段
            if status == TaskStatus.RUNNING.value:
                update_data["started_at"] = datetime.utcnow()
            elif status in [TaskStatus.COMPLETED.value, TaskStatus.FAILED.value]:
                update_data["completed_at"] = datetime.utcnow()
            
            # 添加额外参数
            for key, value in kwargs.items():
                if key in ['error_message', 'result_count', 'current_retry']:
                    update_data[key] = value
            
            result = await self.tasks_collection.update_one(
                {"task_id": task_id},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                logger.info(f"任务 {task_id} 状态更新为 {status}")
                return True
            else:
                logger.warning(f"任务 {task_id} 状态更新失败，未找到任务")
                return False
                
        except Exception as e:
            logger.error(f"更新任务状态失败: {e}")
            return False
    
    async def save_task(self, task: Task) -> bool:
        """保存任务"""
        if not self.initialized or self.tasks_collection is None:
            logger.error("任务管理器未初始化")
            return False
        
        try:
            # 转换Task对象为字典
            task_dict = task.model_dump()
            
            # 设置时间戳
            now = datetime.utcnow()
            if not task_dict.get('created_at'):
                task_dict['created_at'] = now
            task_dict['updated_at'] = now
            
            # 使用upsert插入或更新
            result = await self.tasks_collection.update_one(
                {"task_id": task.task_id},
                {"$set": task_dict},
                upsert=True
            )
            
            if result.upserted_id or result.modified_count > 0:
                logger.info(f"任务 {task.task_id} 保存成功")
                return True
            else:
                logger.warning(f"任务 {task.task_id} 保存失败")
                return False
                
        except Exception as e:
            logger.error(f"保存任务失败: {e}")
            return False
    
    async def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        if not self.initialized or self.tasks_collection is None:
            logger.error("任务管理器未初始化")
            return None
        
        try:
            doc = await self.tasks_collection.find_one({"task_id": task_id})
            if not doc:
                return None
            
            # 移除MongoDB的_id字段
            doc.pop('_id', None)
            
            # 处理datetime字段
            for field in ['created_at', 'updated_at', 'started_at', 'completed_at']:
                if field in doc and doc[field]:
                    if isinstance(doc[field], str):
                        try:
                            doc[field] = datetime.fromisoformat(doc[field].replace('Z', '+00:00'))
                        except:
                            doc[field] = None
            
            return Task(**doc)
            
        except Exception as e:
            logger.error(f"获取任务失败: {e}")
            return None
    
    async def cleanup(self) -> None:
        """清理资源"""
        try:
            if self.client:
                self.client.close()
                logger.info("MongoDB连接已关闭")
        except Exception as e:
            logger.error(f"清理MongoDB连接失败: {e}")
        finally:
            self.client = None
            self.db = None
            self.tasks_collection = None
            self.initialized = False
    
    async def reset_running_tasks(self) -> int:
        """重置所有运行中的任务状态为待处理（用于系统重启时）"""
        if not self.initialized or self.tasks_collection is None:
            return 0
        
        try:
            result = await self.tasks_collection.update_many(
                {"status": TaskStatus.RUNNING.value},
                {
                    "$set": {
                        "status": TaskStatus.PENDING.value,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.info(f"重置了 {result.modified_count} 个运行中的任务状态")
            
            return result.modified_count
            
        except Exception as e:
            logger.error(f"重置运行中任务失败: {e}")
            return 0
    
    async def update_heartbeat(self, task_id: str, progress: float = None) -> bool:
        """更新任务心跳和进度"""
        if not self.initialized or self.tasks_collection is None:
            return False
        
        try:
            update_data = {
                "last_heartbeat": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            if progress is not None:
                update_data["progress"] = min(max(progress, 0.0), 1.0)  # 确保在0-1范围内
            
            result = await self.tasks_collection.update_one(
                {"task_id": task_id},
                {"$set": update_data}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"更新任务心跳失败: {e}")
            return False
    
    async def cleanup_stale_tasks(self, timeout_minutes: int = 60) -> int:
        """清理僵尸任务（长时间无心跳的运行中任务）"""
        if not self.initialized or self.tasks_collection is None:
            return 0
        
        try:
            timeout_time = datetime.utcnow() - timedelta(minutes=timeout_minutes)
            
            # 查找长时间无心跳的运行中任务
            query = {
                "status": TaskStatus.RUNNING.value,
                "$or": [
                    {"last_heartbeat": {"$lt": timeout_time}},
                    {"last_heartbeat": {"$exists": False}},
                    {"started_at": {"$lt": timeout_time}}
                ]
            }
            
            result = await self.tasks_collection.update_many(
                query,
                {
                    "$set": {
                        "status": TaskStatus.FAILED.value,
                        "error_message": f"任务超时（{timeout_minutes}分钟无心跳）",
                        "completed_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            if result.modified_count > 0:
                logger.warning(f"清理了 {result.modified_count} 个僵尸任务")
            
            return result.modified_count
            
        except Exception as e:
            logger.error(f"清理僵尸任务失败: {e}")
            return 0
    
    async def get_task_stats(self) -> Dict[str, Any]:
        """获取任务统计信息"""
        if not self.initialized or self.tasks_collection is None:
            return {}
        
        try:
            # 按状态统计
            pipeline = [
                {"$group": {"_id": "$status", "count": {"$sum": 1}}},
                {"$sort": {"_id": 1}}
            ]
            
            stats = {"total": 0, "by_status": {}}
            async for doc in self.tasks_collection.aggregate(pipeline):
                status = doc["_id"]
                count = doc["count"]
                stats["by_status"][status] = count
                stats["total"] += count
            
            # 按平台统计
            platform_pipeline = [
                {"$group": {"_id": "$platform", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            
            stats["by_platform"] = {}
            async for doc in self.tasks_collection.aggregate(platform_pipeline):
                platform = doc["_id"]
                count = doc["count"]
                stats["by_platform"][platform] = count
            
            return stats
            
        except Exception as e:
            logger.error(f"获取任务统计信息失败: {e}")
            return {}