# GhostWriter Pro HotStream

一个现代化的纯数据库驱动多平台数据抓取框架，使用 Python、Playwright 和 MongoDB 技术构建，支持插件化扩展。

## 架构特点

- 🎯 **纯数据库驱动**: 所有任务管理和状态更新都通过 MongoDB，无需API接口
- 🚀 **多平台支持**: Twitter (基于Nitter)、Medium、知乎、掘金等平台
- 🔌 **插件化架构**: 解耦的平台适配器、数据提取器和存储适配器
- ⏰ **智能调度**: 10秒轮询普通任务，3秒检查高优先级任务
- 🎯 **优先级管理**: 支持1-10级优先级和立即执行标记
- 💔 **容错机制**: 心跳监控、僵尸任务清理、自动重试
- 📊 **实时监控**: 进度跟踪、状态监控、统计信息
- 🔄 **分布式友好**: 支持多实例部署，天然支持水平扩展
- 💾 **数据完整性**: 所有操作都有事务保证，避免数据丢失

## 工作流程

### 1. 任务创建阶段
用户通过CLI或直接在数据库中插入任务记录：
```bash
# 创建Twitter搜索任务
python -m hotstream.cli create-task search_001 search twitter \
  --keywords "AI,机器学习" --priority 1 --immediate --limit 100

# 创建Twitter监控任务
python -m hotstream.cli create-task monitor_001 monitor twitter \
  --accounts "openai,elonmusk" --priority 3 --limit 50
```

### 2. 任务调度阶段
框架运行三个并行的调度循环：
- **主循环(10秒)**: 检查普通优先级任务 (priority > 3)
- **优先级循环(3秒)**: 检查高优先级任务 (priority ≤ 3) 和立即执行任务
- **维护循环(30秒)**: 清理僵尸任务，更新心跳

### 3. 任务执行阶段
```
1. 从MongoDB获取待处理任务 (status=0)
2. 更新任务状态为运行中 (status=1)，设置worker_id
3. 根据平台获取对应的适配器 (TwitterAdapter)
4. 执行数据采集，实时更新progress (0.2-0.6)
5. 使用数据提取器转换为统一格式 (0.6-0.8)
6. 保存到存储适配器 (MongoDB/JSON) (0.8-0.9)
7. 更新任务状态为完成 (status=2)，设置result_count
8. 最终进度设为100%
```

### 4. 状态监控
- **心跳更新**: 每处理10条数据更新一次心跳和进度
- **僵尸检测**: 超过1小时无心跳的任务将被标记为失败
- **自动重试**: 失败任务可根据retry_count自动重试
- **实时进度**: 0%-20%(初始化) → 20%-60%(数据采集) → 60%-80%(数据处理) → 80%-90%(存储) → 100%(完成)

## 数据库字段定义

### tasks 集合 (MongoDB)

| 字段名 | 类型 | 描述 | 示例 |
|--------|------|------|------|
| task_id | String | 任务唯一标识 | "search_001" |
| name | String | 任务名称 | "Twitter AI搜索" |
| platform | String | 平台名称 | "twitter" |
| task_type | String | 任务类型 | "search" / "monitor" |
| keywords | Array | 搜索关键字 | ["AI", "机器学习"] |
| accounts | Array | 监控账号 | ["openai", "elonmusk"] |
| schedule | String | 定时计划(Cron) | "0 9 * * *" |
| status | Integer | 任务状态 | 0=pending, 1=running, 2=completed, 3=failed, 4=cancelled |
| priority | Integer | 优先级 | 1=最高, 10=最低, 5=普通 |
| immediate | Boolean | 立即执行标记 | true / false |
| options | Object | 任务选项 | {"limit": 100} |
| storage_config | Object | 存储配置 | {"type": "mongodb"} |
| retry_count | Integer | 最大重试次数 | 3 |
| current_retry | Integer | 当前重试次数 | 0 |
| timeout | Integer | 超时时间(秒) | 3600 |
| created_at | DateTime | 创建时间 | 2025-01-01T00:00:00Z |
| updated_at | DateTime | 更新时间 | 2025-01-01T00:05:00Z |
| started_at | DateTime | 开始时间 | 2025-01-01T00:10:00Z |
| completed_at | DateTime | 完成时间 | 2025-01-01T00:15:00Z |
| last_heartbeat | DateTime | 最后心跳 | 2025-01-01T00:12:30Z |
| error_message | String | 错误信息 | "网络连接超时" |
| result_count | Integer | 结果数量 | 85 |
| progress | Float | 进度百分比 | 0.75 (75%) |
| worker_id | String | 工作进程ID | "worker_140234567890" |

### data_items 集合 (MongoDB)

| 字段名 | 类型 | 描述 | 示例 |
|--------|------|------|------|
| id | String | 数据唯一标识 | "twitter_abc123456" |
| platform | String | 来源平台 | "twitter" |
| content | String | 内容文本 | "OpenAI发布了新的模型..." |
| author | String | 作者/用户名 | "openai" |
| url | String | 原始链接 | "https://twitter.com/openai/status/123" |
| created_at | String | 创建时间 | "2025-01-01T00:00:00Z" |
| metadata | Object | 元数据 | {"like_count": 100, "retweet_count": 50} |
| raw_data | Object | 原始数据 | {...} |
| saved_at | DateTime | 保存时间 | 2025-01-01T00:15:00Z |

## 快速开始

### 1. 环境安装

```bash
# 安装依赖
pip install -r requirements.txt
playwright install

# 启动MongoDB (Docker方式)
docker run -d --name mongodb -p 27017:27017 mongo:latest
```

### 2. 配置文件

在 `configs/hotstream.yaml` 中配置：

```yaml
framework:
  name: "HotStream"
  debug: false
  log_level: "INFO"

mongodb:
  enabled: true
  uri: "mongodb://localhost:27017"
  database: "hotstream"

scheduler:
  check_interval: 10           # 主循环间隔(秒)
  max_concurrent_tasks: 5      # 最大并发任务数
  task_timeout: 3600          # 任务超时时间(秒)

platforms:
  twitter:
    enabled: true
    rate_limit:
      requests_per_minute: 100

storage:
  default_type: "mongodb"
  output_dir: "output"
```

### 3. 启动数据处理守护进程

```bash
# 启动守护进程，开始处理数据库中的任务
python -m hotstream.cli start-daemon
```

### 4. 创建任务

```bash
# 创建搜索任务
python -m hotstream.cli create-task search_ai search twitter \
  --keywords "人工智能,机器学习" \
  --priority 1 \
  --immediate \
  --limit 100

# 创建监控任务
python -m hotstream.cli create-task monitor_tech monitor twitter \
  --accounts "openai,anthropicai" \
  --priority 3 \
  --limit 50 \
  --storage mongodb

# 查看任务统计
python -m hotstream.cli task-stats
```

### 5. 直接操作数据库

也可以直接在MongoDB中插入任务：

```javascript
// 在MongoDB中直接创建任务
db.tasks.insertOne({
  "task_id": "search_002",
  "name": "科技新闻搜索",
  "platform": "twitter",
  "task_type": "search",
  "keywords": ["科技", "创新"],
  "status": 0,
  "priority": 5,
  "immediate": false,
  "options": {"limit": 50},
  "storage_config": {"type": "mongodb"},
  "retry_count": 3,
  "current_retry": 0,
  "timeout": 3600,
  "created_at": new Date(),
  "updated_at": new Date()
});

// 查询任务状态
db.tasks.find(
  {"status": {"$in": [0, 1]}}, 
  {"task_id": 1, "status": 1, "progress": 1, "last_heartbeat": 1}
).sort({"priority": 1, "created_at": 1});

// 手动设置任务为高优先级
db.tasks.updateOne(
  {"task_id": "search_002"}, 
  {"$set": {"priority": 1, "immediate": true}}
);
```

## 命令行工具

```bash
# 创建任务
  1. 创建搜索任务（推荐用这个测试）：
  python -m hotstream.cli create-task search_ai_ml search twitter -k "AI,机器学习,深度学习" -l 30 -n "AI技术搜索" --immediate

  2. 创建普通搜索任务：
  python -m hotstream.cli create-task task_001 search twitter -k "Python,编程" -l 50 -p 3

  3. 创建监控任务：
  python -m hotstream.cli create-task monitor_tech monitor twitter -a "elonmusk,sundarpichai" -l 20 -n "科技大佬监控"

  4. 创建高优先级立即执行任务：
  python -m hotstream.cli create-task urgent_search search twitter -k "ChatGPT,OpenAI" -l 100 -p 1 --immediate


# 启动守护进程
hotstream start-daemon

# 查看任务统计
hotstream task-stats

# 查看框架信息
hotstream info

# 测试Nitter连接
hotstream test-nitter openai --limit 5
```

### 创建任务参数

| 参数 | 描述 | 示例 |
|------|------|------|
| --keywords, -k | 搜索关键字 | "AI,机器学习" |
| --accounts, -a | 监控账号 | "openai,elonmusk" |
| --priority, -p | 优先级(1-10) | 1 |
| --immediate | 立即执行 | --immediate |
| --limit, -l | 数据限制 | 100 |
| --storage | 存储类型 | mongodb/json |
| --name, -n | 任务名称 | "AI新闻搜索" |

## 项目结构

```
hotstream/
├── core/                      # 核心框架
│   ├── interfaces.py         # 接口定义和数据模型
│   ├── framework.py          # 主框架
│   ├── enhanced_scheduler.py # 增强型调度器
│   ├── task_manager.py       # MongoDB任务管理器
│   ├── plugin_manager.py     # 插件管理器
│   └── data_processor.py     # 数据处理器
├── plugins/                   # 插件目录
│   ├── platforms/            # 平台适配器
│   │   └── twitter_adapter.py # Twitter/Nitter适配器
│   ├── extractors/           # 数据提取器
│   │   └── base_extractor.py # 基础提取器
│   └── storages/             # 存储适配器
│       ├── mongo_storage.py  # MongoDB存储
│       └── json_storage.py   # JSON文件存储
├── config/                   # 配置管理
└── cli.py                    # 命令行界面
```

## 插件开发

### 平台适配器

```python
from hotstream.core.interfaces import PlatformAdapter, DataItem

class MyPlatformAdapter(PlatformAdapter):
    platform_name = "myplatform"
    
    async def authenticate(self, credentials):
        # 实现认证逻辑
        return True
    
    async def search(self, keywords, options):
        # 实现搜索逻辑
        for result in search_results:
            yield DataItem(
                id=result.id,
                platform=self.platform_name,
                content=result.content,
                author=result.author,
                url=result.url,
                created_at=result.timestamp
            )
```

### 数据提取器

```python
from hotstream.core.interfaces import DataExtractor, DataItem

class MyDataExtractor(DataExtractor):
    async def extract(self, raw_data):
        # 提取和标准化数据
        return DataItem(...)
    
    def validate(self, data):
        # 验证数据有效性
        return len(data.content) > 10
```

### 存储适配器

```python
from hotstream.core.interfaces import StorageAdapter

class MyStorageAdapter(StorageAdapter):
    async def save(self, items):
        # 保存数据逻辑
        return True
    
    async def query(self, filters):
        # 查询数据逻辑
        return []
```

## 监控和调试

### 任务状态监控

```bash
# 查看实时统计
python -m hotstream.cli task-stats

# 查看MongoDB中的任务
mongo hotstream --eval "db.tasks.find({}, {task_id:1, status:1, progress:1, updated_at:1})"

# 查看正在运行的任务
mongo hotstream --eval "db.tasks.find({status: 1}, {task_id:1, progress:1, last_heartbeat:1, worker_id:1})"

# 查看失败的任务
mongo hotstream --eval "db.tasks.find({status: 3}, {task_id:1, error_message:1, current_retry:1})"

# 清理僵尸任务（可选）
mongo hotstream --eval "db.tasks.updateMany({status: 1, last_heartbeat: {\$lt: new Date(Date.now() - 3600000)}}, {\$set: {status: 3, error_message: '任务超时'}})"
```

### 日志配置

框架使用 loguru 进行日志记录，可在配置文件中设置：

```yaml
framework:
  log_level: "INFO"  # DEBUG, INFO, WARNING, ERROR

monitoring:
  log_file: "logs/hotstream.log"
  log_rotation: "1 day"
  log_retention: "30 days"
```

## 性能优化

### 并发控制
- `max_concurrent_tasks`: 控制同时运行的任务数量
- `check_interval`: 调整轮询频率
- `priority_check_interval`: 高优先级任务检查频率

### 存储优化
- 使用MongoDB索引提升查询性能
- 批量保存数据减少IO开销
- 配置合适的batch_size

### 网络优化
- 配置请求间隔避免限流
- 使用代理轮换提高成功率
- 实现指数退避重试策略

## 容器化部署

### Docker Compose

```yaml
version: '3.8'
services:
  hotstream:
    build: .
    depends_on:
      - mongodb
    environment:
      - MONGODB_URI=mongodb://mongodb:27017
    volumes:
      - ./output:/app/output
      - ./logs:/app/logs

  mongodb:
    image: mongo:latest
    ports:
      - "27017:27017"
    volumes:
      - mongodb_data:/data/db

volumes:
  mongodb_data:
```

## 注意事项

- ⚠️ 请遵守各平台的服务条款和robots.txt
- ⚠️ 建议配置合理的请求间隔避免被限流
- ⚠️ 敏感数据建议加密存储
- ⚠️ 生产环境请配置日志轮转和监控
- ⚠️ Twitter数据通过Nitter获取，请选择稳定的Nitter实例

## 故障排除

### 常见问题

1. **任务一直处于运行状态**
   - 检查心跳更新是否正常: `db.tasks.find({status: 1}, {task_id:1, last_heartbeat:1})`
   - 查看是否有僵尸任务需要清理
   - 检查worker_id是否还在运行

2. **MongoDB连接失败**
   - 检查MongoDB服务是否启动: `systemctl status mongod`
   - 验证连接字符串是否正确
   - 检查网络防火墙设置

3. **Nitter连接失败**
   - 尝试更换Nitter实例: `https://nitter.net`, `https://nitter.it`
   - 检查网络连接和防火墙设置
   - 验证Nitter实例是否可用

4. **任务重复执行**
   - 确保只有一个守护进程在运行
   - 检查任务状态是否正确更新
   - 验证任务ID是否唯一

5. **数据采集失败**
   - 检查平台适配器是否正常工作
   - 验证网络连接和代理设置
   - 查看错误日志了解具体原因

### 调试技巧

```bash
# 在前端启动
python -m hotstream.cli
# 启动守护进程模式启动
python -m hotstream.cli --daemon

# 查看详细日志
tail -f logs/hotstream.log

# 测试平台连接
python -m hotstream.cli test-nitter openai --limit 1

# 手动触发任务
db.tasks.updateOne({"task_id": "your_task"}, {"$set": {"immediate": true}})
```

## 最佳实践

### 生产环境部署

1. **数据库优化**
   ```javascript
   // 创建复合索引提升查询性能
   db.tasks.createIndex({"status": 1, "priority": 1, "created_at": 1})
   db.tasks.createIndex({"immediate": 1, "status": 1})
   db.data_items.createIndex({"platform": 1, "created_at": -1})
   ```

2. **监控设置**
   ```bash
   # 设置MongoDB监控
   mongostat --host localhost:27017
   
   # 设置任务监控脚本
   watch -n 5 'mongo hotstream --eval "db.tasks.aggregate([{\$group: {_id: \"\$status\", count: {\$sum: 1}}}])"'
   ```

3. **性能调优**
   - 根据服务器性能调整 `max_concurrent_tasks`
   - 设置合适的 `check_interval` 平衡响应速度和CPU使用
   - 配置MongoDB连接池大小

### 多实例部署

```yaml
# docker-compose-cluster.yml
version: '3.8'
services:
  hotstream-worker-1:
    build: .
    environment:
      - WORKER_ID=worker-1
      - MONGODB_URI=mongodb://mongodb:27017

  hotstream-worker-2:
    build: .
    environment:
      - WORKER_ID=worker-2
      - MONGODB_URI=mongodb://mongodb:27017

  mongodb:
    image: mongo:latest
    command: mongod --replSet rs0
    volumes:
      - mongodb_data:/data/db
```

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 技术支持

如遇到问题，请提供以下信息：
- 错误日志
- 任务配置
- MongoDB查询结果
- 系统环境信息