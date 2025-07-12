"""
通用数据提取器
"""

import re
import hashlib
from datetime import datetime
from typing import Dict, Any, List
from loguru import logger

from ...core.interfaces import DataExtractor, DataItem


class BaseDataExtractor(DataExtractor):
    """基础数据提取器"""
    
    def __init__(self, platform: str):
        self.platform = platform
        self.content_filters = [
            self._remove_excessive_whitespace,
            self._remove_urls_if_needed,
            self._normalize_text
        ]
    
    async def extract(self, raw_data: Dict[str, Any]) -> DataItem:
        """从原始数据提取标准化数据项"""
        try:
            # 基本字段提取
            content = self._extract_content(raw_data)
            author = self._extract_author(raw_data)
            url = self._extract_url(raw_data)
            created_at = self._extract_created_at(raw_data)
            
            # 生成唯一ID
            item_id = self._generate_id(content, author, created_at)
            
            # 应用内容过滤器
            content = self._apply_content_filters(content)
            
            # 提取元数据
            metadata = self._extract_metadata(raw_data)
            
            # 创建数据项
            item = DataItem(
                id=item_id,
                platform=self.platform,
                content=content,
                author=author,
                url=url,
                created_at=created_at,
                metadata=metadata,
                raw_data=raw_data
            )
            
            logger.debug(f"提取数据项: {item.id} - {content[:50]}...")
            return item
            
        except Exception as e:
            logger.error(f"数据提取失败: {e}")
            raise
    
    def validate(self, data: DataItem) -> bool:
        """验证数据项"""
        try:
            # 基本字段验证
            if not data.id or not data.platform or not data.content:
                logger.warning(f"数据项缺少必要字段: {data.id}")
                return False
            
            # 内容长度验证
            if len(data.content.strip()) < 5:
                logger.warning(f"内容过短: {data.id}")
                return False
            
            # 平台验证
            if data.platform != self.platform:
                logger.warning(f"平台不匹配: {data.platform} != {self.platform}")
                return False
            
            # 自定义验证
            if not self._custom_validate(data):
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"数据验证失败: {e}")
            return False
    
    def _extract_content(self, raw_data: Dict[str, Any]) -> str:
        """提取内容 - 子类可重写"""
        return raw_data.get('content', raw_data.get('text', ''))
    
    def _extract_author(self, raw_data: Dict[str, Any]) -> str:
        """提取作者 - 子类可重写"""
        return raw_data.get('author', raw_data.get('username', ''))
    
    def _extract_url(self, raw_data: Dict[str, Any]) -> str:
        """提取URL - 子类可重写"""
        return raw_data.get('url', raw_data.get('link', ''))
    
    def _extract_created_at(self, raw_data: Dict[str, Any]) -> str:
        """提取创建时间 - 子类可重写"""
        created_at = raw_data.get('created_at', raw_data.get('timestamp', ''))
        
        # 如果没有时间戳，使用当前时间
        if not created_at:
            created_at = datetime.utcnow().isoformat() + 'Z'
        
        return created_at
    
    def _extract_metadata(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """提取元数据 - 子类可重写"""
        metadata = {}
        
        # 常见的社交媒体指标
        for key in ['like_count', 'retweet_count', 'reply_count', 'share_count', 
                   'view_count', 'comment_count', 'favorite_count']:
            if key in raw_data:
                metadata[key] = raw_data[key]
        
        # 其他可能有用的字段
        for key in ['language', 'location', 'hashtags', 'mentions', 'verified']:
            if key in raw_data:
                metadata[key] = raw_data[key]
        
        return metadata
    
    def _generate_id(self, content: str, author: str, created_at: str) -> str:
        """生成唯一ID"""
        # 使用内容、作者和时间生成哈希
        content_hash = hashlib.md5(
            f"{content}{author}{created_at}".encode('utf-8')
        ).hexdigest()[:12]
        
        return f"{self.platform}_{content_hash}"
    
    def _apply_content_filters(self, content: str) -> str:
        """应用内容过滤器"""
        for filter_func in self.content_filters:
            content = filter_func(content)
        return content
    
    def _remove_excessive_whitespace(self, text: str) -> str:
        """移除多余的空白字符"""
        # 替换多个连续的空白字符为单个空格
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _remove_urls_if_needed(self, text: str) -> str:
        """如果需要，移除URL（默认保留）"""
        # 这里可以根据需要移除URL
        # text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        return text
    
    def _normalize_text(self, text: str) -> str:
        """文本标准化"""
        # 移除控制字符
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\r\t')
        return text
    
    def _custom_validate(self, data: DataItem) -> bool:
        """自定义验证 - 子类可重写"""
        return True


class TwitterDataExtractor(BaseDataExtractor):
    """Twitter专用数据提取器"""
    
    def __init__(self):
        super().__init__("twitter")
    
    def _extract_metadata(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Twitter专用元数据提取"""
        metadata = super()._extract_metadata(raw_data)
        
        # Twitter特有字段
        twitter_fields = [
            'retweet_count', 'like_count', 'reply_count', 'quote_count',
            'is_retweet', 'is_quote', 'hashtags', 'mentions', 'urls',
            'media_urls', 'poll_data', 'thread_position'
        ]
        
        for field in twitter_fields:
            if field in raw_data:
                metadata[field] = raw_data[field]
        
        # 从Nitter适配器获取的特殊字段
        if 'nitter_instance' in raw_data:
            metadata['nitter_instance'] = raw_data['nitter_instance']
        
        if 'keyword' in raw_data:
            metadata['search_keyword'] = raw_data['keyword']
        
        return metadata
    
    def _custom_validate(self, data: DataItem) -> bool:
        """Twitter专用验证"""
        # 检查是否为垃圾推文
        content = data.content.lower()
        
        # 过滤掉过短的推文
        if len(data.content.strip()) < 10:
            return False
        
        # 过滤掉纯广告推文（简单规则）
        spam_indicators = ['buy now', 'click here', 'follow for follow', 
                          '100% guaranteed', 'make money fast']
        
        if any(indicator in content for indicator in spam_indicators):
            logger.warning(f"检测到垃圾推文: {data.id}")
            return False
        
        return True


class MediumDataExtractor(BaseDataExtractor):
    """Medium专用数据提取器"""
    
    def __init__(self):
        super().__init__("medium")
    
    def _extract_metadata(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Medium专用元数据提取"""
        metadata = super()._extract_metadata(raw_data)
        
        # Medium特有字段
        medium_fields = [
            'claps', 'responses', 'read_time', 'publication', 
            'tags', 'subtitle', 'featured_image'
        ]
        
        for field in medium_fields:
            if field in raw_data:
                metadata[field] = raw_data[field]
        
        return metadata


class ZhihuDataExtractor(BaseDataExtractor):
    """知乎专用数据提取器"""
    
    def __init__(self):
        super().__init__("zhihu")
    
    def _extract_metadata(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """知乎专用元数据提取"""
        metadata = super()._extract_metadata(raw_data)
        
        # 知乎特有字段
        zhihu_fields = [
            'voteup_count', 'comment_count', 'answer_count',
            'follower_count', 'question_id', 'answer_id',
            'excerpt', 'topics'
        ]
        
        for field in zhihu_fields:
            if field in raw_data:
                metadata[field] = raw_data[field]
        
        return metadata


class JuejinDataExtractor(BaseDataExtractor):
    """掘金专用数据提取器"""
    
    def __init__(self):
        super().__init__("juejin")
    
    def _extract_metadata(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """掘金专用元数据提取"""
        metadata = super()._extract_metadata(raw_data)
        
        # 掘金特有字段
        juejin_fields = [
            'digg_count', 'view_count', 'comment_count',
            'collect_count', 'tags', 'category', 'level'
        ]
        
        for field in juejin_fields:
            if field in raw_data:
                metadata[field] = raw_data[field]
        
        return metadata