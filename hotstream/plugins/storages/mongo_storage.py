"""
MongoDB 存储适配器
"""

from datetime import datetime
from typing import Dict, List, Any, Optional
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection

from ...core.interfaces import StorageAdapter, DataItem


class MongoStorageAdapter(StorageAdapter):
    """MongoDB 存储适配器"""
    
    def __init__(self, mongo_uri: str = "mongodb://localhost:27017", 
                 db_name: str = "hotstream", **kwargs):
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None
        self.collection: Optional[AsyncIOMotorCollection] = None
        self.initialized = False
        
        # 配置选项
        self.collection_name = kwargs.get('collection_name', 'data_items')
        self.batch_size = kwargs.get('batch_size', 1000)
        
        logger.info(f"MongoDB 存储适配器初始化: {mongo_uri}/{db_name}")
    
    async def initialize(self) -> bool:
        """初始化MongoDB连接"""
        try:
            self.client = AsyncIOMotorClient(self.mongo_uri)
            self.db = self.client[self.db_name]
            self.collection = self.db[self.collection_name]
            
            # 创建索引
            await self._create_indexes()
            
            # 测试连接
            await self.client.admin.command('ping')
            
            self.initialized = True
            logger.info(f"MongoDB 存储适配器连接成功: {self.mongo_uri}")
            return True
            
        except Exception as e:
            logger.error(f"MongoDB 存储适配器初始化失败: {e}")
            return False
    
    async def _create_indexes(self):
        """创建数据库索引"""
        try:
            # 创建唯一索引
            await self.collection.create_index("id", unique=True)
            
            # 创建查询索引
            await self.collection.create_index("platform")
            await self.collection.create_index("author")
            await self.collection.create_index("created_at")
            await self.collection.create_index("task_id")
            await self.collection.create_index([("platform", 1), ("created_at", -1)])
            await self.collection.create_index([("platform", 1), ("author", 1)])
            await self.collection.create_index([("task_id", 1), ("created_at", -1)])
            
            # 全文索引
            await self.collection.create_index([("content", "text")])
            
            logger.info("MongoDB 索引创建完成")
            
        except Exception as e:
            logger.warning(f"创建索引时出现警告: {e}")
    
    async def save(self, items: List[DataItem], task_id: Optional[str] = None) -> bool:
        """保存数据到 MongoDB"""
        if not self.initialized:
            if not await self.initialize():
                return False
        
        if not items:
            logger.warning("没有数据需要保存")
            return True
        
        try:
            # 转换为字典格式
            documents = []
            for item in items:
                doc = item.model_dump()
                doc['saved_at'] = datetime.utcnow()
                if task_id:
                    doc['task_id'] = task_id
                documents.append(doc)
            
            # 批量插入，处理重复数据
            inserted_count = 0
            duplicate_count = 0
            
            # 分批处理
            for i in range(0, len(documents), self.batch_size):
                batch = documents[i:i + self.batch_size]
                
                try:
                    result = await self.collection.insert_many(
                        batch, 
                        ordered=False  # 允许部分失败
                    )
                    inserted_count += len(result.inserted_ids)
                    
                except Exception as batch_error:
                    # 处理重复键错误
                    if "duplicate key" in str(batch_error).lower():
                        # 逐个插入来处理重复数据
                        for doc in batch:
                            try:
                                await self.collection.insert_one(doc)
                                inserted_count += 1
                            except Exception as single_error:
                                if "duplicate key" in str(single_error).lower():
                                    duplicate_count += 1
                                else:
                                    logger.error(f"插入单个文档失败: {single_error}")
                    else:
                        logger.error(f"批量插入失败: {batch_error}")
                        return False
            
            total_items = len(items)
            logger.info(f"MongoDB 保存完成: 总数 {total_items}, 新增 {inserted_count}, 重复 {duplicate_count}")
            
            return True
            
        except Exception as e:
            logger.error(f"MongoDB 存储失败: {e}")
            return False
    
    async def query(self, filters: Dict[str, Any]) -> List[DataItem]:
        """查询数据"""
        if not self.initialized:
            if not await self.initialize():
                return []
        
        try:
            # 构建查询条件
            query = self._build_query(filters)
            
            # 分页参数
            limit = filters.get('limit', 1000)
            skip = filters.get('skip', 0)
            
            # 排序
            sort_field = filters.get('sort_by', 'created_at')
            sort_order = -1 if filters.get('sort_desc', True) else 1
            
            cursor = self.collection.find(query).sort(sort_field, sort_order).skip(skip).limit(limit)
            
            results = []
            async for doc in cursor:
                # 移除MongoDB的_id字段
                doc.pop('_id', None)
                doc.pop('saved_at', None)
                
                try:
                    item = DataItem(**doc)
                    results.append(item)
                except Exception as item_error:
                    logger.warning(f"解析数据项失败: {item_error}")
                    continue
            
            logger.info(f"MongoDB 查询完成: 返回 {len(results)} 条数据")
            return results
            
        except Exception as e:
            logger.error(f"MongoDB 查询失败: {e}")
            return []
    
    def _build_query(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        """构建MongoDB查询条件"""
        query = {}
        
        # 基本字段查询
        for field in ['platform', 'author', 'id']:
            if field in filters:
                query[field] = filters[field]
        
        # 时间范围查询
        if 'since' in filters or 'until' in filters:
            query['created_at'] = {}
            if 'since' in filters:
                query['created_at']['$gte'] = filters['since']
            if 'until' in filters:
                query['created_at']['$lte'] = filters['until']
        
        # 文本搜索
        if 'search_text' in filters:
            query['$text'] = {'$search': filters['search_text']}
        
        # 内容包含查询
        if 'content_contains' in filters:
            query['content'] = {'$regex': filters['content_contains'], '$options': 'i'}
        
        # 元数据查询
        if 'metadata' in filters:
            for key, value in filters['metadata'].items():
                query[f'metadata.{key}'] = value
        
        # 自定义查询条件
        if 'custom_query' in filters:
            query.update(filters['custom_query'])
        
        return query
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取存储统计信息"""
        if not self.initialized:
            return {}
        
        try:
            # 总数统计
            total_count = await self.collection.count_documents({})
            
            # 按平台统计
            platform_pipeline = [
                {"$group": {"_id": "$platform", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            
            platform_stats = {}
            async for doc in self.collection.aggregate(platform_pipeline):
                platform_stats[doc["_id"]] = doc["count"]
            
            # 按日期统计（最近7天）
            from datetime import timedelta
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=7)
            
            date_pipeline = [
                {
                    "$match": {
                        "created_at": {
                            "$gte": start_date.isoformat(),
                            "$lte": end_date.isoformat()
                        }
                    }
                },
                {
                    "$group": {
                        "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": {"$dateFromString": {"dateString": "$created_at"}}}},
                        "count": {"$sum": 1}
                    }
                },
                {"$sort": {"_id": 1}}
            ]
            
            daily_stats = {}
            async for doc in self.collection.aggregate(date_pipeline):
                daily_stats[doc["_id"]] = doc["count"]
            
            return {
                "total_count": total_count,
                "platform_stats": platform_stats,
                "daily_stats": daily_stats
            }
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}
    
    async def delete_by_filters(self, filters: Dict[str, Any]) -> int:
        """根据条件删除数据"""
        if not self.initialized:
            return 0
        
        try:
            query = self._build_query(filters)
            result = await self.collection.delete_many(query)
            
            deleted_count = result.deleted_count
            logger.info(f"删除了 {deleted_count} 条数据")
            return deleted_count
            
        except Exception as e:
            logger.error(f"删除数据失败: {e}")
            return 0
    
    async def update_by_filters(self, filters: Dict[str, Any], updates: Dict[str, Any]) -> int:
        """根据条件更新数据"""
        if not self.initialized:
            return 0
        
        try:
            query = self._build_query(filters)
            update_doc = {"$set": updates}
            
            result = await self.collection.update_many(query, update_doc)
            
            updated_count = result.modified_count
            logger.info(f"更新了 {updated_count} 条数据")
            return updated_count
            
        except Exception as e:
            logger.error(f"更新数据失败: {e}")
            return 0
    
    async def close(self) -> None:
        """关闭连接"""
        try:
            if self.client:
                self.client.close()
                logger.info("MongoDB 连接已关闭")
        except Exception as e:
            logger.error(f"关闭 MongoDB 连接失败: {e}")
        finally:
            self.client = None
            self.db = None
            self.collection = None
            self.initialized = False