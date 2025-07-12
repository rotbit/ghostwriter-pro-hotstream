# GhostWriter Pro HotStream

一个现代化的多平台数据抓取框架，使用 Python 和 Playwright 技术构建，支持插件化扩展。

## 特性

- 🚀 **多平台支持**: Twitter、Medium、知乎、掘金等主流平台
- 🔌 **插件化架构**: 易于扩展新平台和存储方式
- ⏰ **定时任务**: 支持 Cron 表达式的定时数据采集
- 🎯 **即时搜索**: 根据关键字立即搜索多平台数据
- 💾 **多种存储**: JSON、数据库、云存储等多种存储方案
- 🛡️ **安全可靠**: 内置限流、重试、代理轮换等机制
- 🎨 **友好界面**: 命令行界面和编程接口双重支持

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
playwright install
```

### 基本使用

#### 1. 启动后台服务

```bash
# 启动守护进程模式（推荐）
python -m hotstream.cli start --daemon

# 指定 API 服务地址和端口
python -m hotstream.cli start --daemon --host 0.0.0.0 --port 8000
```

#### 2. 立即搜索

```bash
# 搜索 Twitter 上关于 AI 的内容
python -m hotstream.cli search twitter "AI,机器学习" --limit 50

# 列出支持的平台
python -m hotstream.cli list-platforms
```

#### 3. HTTP API 调用

```bash
# 健康检查
curl http://localhost:8000/health

# 立即搜索
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"platform": "twitter", "keywords": ["AI"], "limit": 10}'

# 创建定时任务
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"task_id": "daily_ai", "name": "每日AI", "platform": "twitter", "keywords": ["AI"], "schedule": "0 9 * * *"}'

# 立即执行任务
curl -X POST http://localhost:8000/tasks/daily_ai/execute
```

#### 4. 编程接口

```python
import asyncio
from hotstream.core.framework import HotStreamFramework

async def main():
    framework = HotStreamFramework()
    await framework.initialize()
    
    # 立即搜索
    results = await framework.execute_immediate_search(
        platform="twitter",
        keywords=["AI", "机器学习"],
        limit=20
    )
    
    print(f"获得 {len(results)} 条数据")
    for item in results[:3]:
        print(f"- {item.content[:100]}...")
    
    await framework.stop()

asyncio.run(main())
```

#### 5. 定时任务

```python
from hotstream.core.interfaces import TaskConfig, SearchOptions

# 创建定时任务
task_config = TaskConfig(
    task_id="daily_tech_news",
    name="每日技术新闻",
    platform="twitter",
    keywords=["技术", "编程", "开发"],
    schedule="0 9 * * *",  # 每天上午9点
    options=SearchOptions(limit=100),
    storage_config={
        "type": "json",
        "output_dir": "output/daily"
    }
)

await framework.add_task(task_config)
```

## 项目结构

```
hotstream/
├── core/                   # 核心框架
│   ├── interfaces.py      # 接口定义
│   ├── framework.py       # 主框架
│   ├── plugin_manager.py  # 插件管理器
│   ├── scheduler.py       # 任务调度器
│   └── data_processor.py  # 数据处理器
├── plugins/               # 插件目录
│   ├── platforms/         # 平台适配器
│   ├── extractors/        # 数据提取器
│   └── storages/          # 存储适配器
├── config/                # 配置管理
└── cli.py                 # 命令行界面
```

## 配置文件

配置文件支持 YAML 和 JSON 格式，放置在 `configs/hotstream.yaml`：

```yaml
framework:
  name: "HotStream"
  debug: false
  log_level: "INFO"

platforms:
  twitter:
    enabled: true
    rate_limit:
      requests_per_minute: 100
      requests_per_hour: 1000

storage:
  default_type: "json"
  output_dir: "output"

crawler:
  timeout: 30
  retry_count: 3
  concurrent_requests: 5
```

## 插件开发

### 平台适配器

```python
from hotstream.core.interfaces import PlatformAdapter, DataItem

class MyPlatformAdapter(PlatformAdapter):
    platform_name = "myplatform"
    
    async def authenticate(self, credentials):
        # 实现认证逻辑
        pass
    
    async def search(self, keywords, options):
        # 实现搜索逻辑
        for result in search_results:
            yield DataItem(
                id=result.id,
                platform=self.platform_name,
                content=result.content,
                # ... 其他字段
            )
```

### 存储适配器

```python
from hotstream.core.interfaces import StorageAdapter

class MyStorageAdapter(StorageAdapter):
    async def save(self, items):
        # 实现保存逻辑
        pass
    
    async def query(self, filters):
        # 实现查询逻辑
        pass
```

## 命令行工具

```bash
# 启动守护进程（后台运行 + API 服务）
hotstream start --daemon

# 启动框架（前台运行）
hotstream start

# 立即搜索
hotstream search twitter "关键字" --limit 100

# 添加定时任务
hotstream add-task my_task twitter "关键字" --schedule "0 */6 * * *"

# 查看框架信息
hotstream info

# 列出支持的平台
hotstream list-platforms
```

## HTTP API 接口

框架提供完整的 REST API 接口：

- `GET /health` - 健康检查
- `POST /search` - 立即搜索
- `GET /platforms` - 获取支持的平台
- `POST /tasks` - 创建任务
- `GET /tasks` - 获取任务列表
- `GET /tasks/{task_id}` - 获取任务详情
- `POST /tasks/{task_id}/execute` - 立即执行任务
- `DELETE /tasks/{task_id}` - 删除任务
- `GET /status` - 获取框架状态

详细的 API 文档可访问：`http://localhost:8000/docs`

## 注意事项

- 请遵守各平台的服务条款和 robots.txt
- 建议配置合理的请求间隔避免被限流
- 敏感数据建议加密存储
- 生产环境请配置日志轮转和监控

## 开发计划

- [ ] 支持更多平台（Reddit、LinkedIn 等）
- [ ] 实现数据去重和内容相似性检测
- [ ] 添加 Web 管理界面
- [ ] 支持分布式部署
- [ ] 增强数据分析和可视化功能

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！