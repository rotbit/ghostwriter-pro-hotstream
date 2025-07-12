"""
命令行界面
"""

import asyncio
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from loguru import logger

from .core.framework import HotStreamFramework
from .core.interfaces import TaskConfig, SearchOptions

app = typer.Typer(help="HotStream - 多平台数据抓取框架")
console = Console()


@app.command()
def start(
    config: Optional[str] = typer.Option(None, "--config", "-c", help="配置文件路径"),
    daemon: bool = typer.Option(False, "--daemon", "-d", help="以守护进程模式运行"),
    host: str = typer.Option("0.0.0.0", "--host", help="API 服务器地址"),
    port: int = typer.Option(8000, "--port", help="API 服务器端口")
):
    """启动 HotStream 框架"""
    if daemon:
        # 守护进程模式
        async def _start_daemon():
            from .daemon import run_daemon
            await run_daemon(config, host, port)
        
        console.print(f"[green]启动 HotStream 守护进程...[/green]")
        asyncio.run(_start_daemon())
    else:
        # 普通模式
        async def _start():
            framework = HotStreamFramework(config)
            await framework.start()
        
        asyncio.run(_start())


@app.command()
def search(
    platform: str = typer.Argument(..., help="平台名称"),
    keywords: str = typer.Argument(..., help="搜索关键字（用逗号分隔）"),
    limit: int = typer.Option(100, "--limit", "-l", help="结果数量限制"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="输出目录")
):
    """立即搜索数据"""
    async def _search():
        framework = HotStreamFramework()
        
        if not await framework.initialize():
            console.print("[red]框架初始化失败[/red]")
            return
        
        keyword_list = [k.strip() for k in keywords.split(",")]
        
        try:
            results = await framework.execute_immediate_search(
                platform=platform,
                keywords=keyword_list,
                limit=limit
            )
            
            console.print(f"[green]搜索完成！获得 {len(results)} 条数据[/green]")
            
            # 显示结果表格
            if results:
                table = Table(title=f"{platform} 搜索结果")
                table.add_column("ID")
                table.add_column("作者")
                table.add_column("内容预览")
                table.add_column("URL")
                
                for item in results[:10]:  # 只显示前10条
                    content_preview = item.content[:50] + "..." if len(item.content) > 50 else item.content
                    table.add_row(
                        item.id,
                        item.author or "N/A",
                        content_preview,
                        item.url or "N/A"
                    )
                
                console.print(table)
                
                if len(results) > 10:
                    console.print(f"[dim]... 还有 {len(results) - 10} 条结果[/dim]")
        
        except Exception as e:
            console.print(f"[red]搜索失败: {e}[/red]")
        
        finally:
            await framework.stop()
    
    asyncio.run(_search())


@app.command()
def list_platforms():
    """列出支持的平台"""
    async def _list_platforms():
        framework = HotStreamFramework()
        
        if not await framework.initialize():
            console.print("[red]框架初始化失败[/red]")
            return
        
        platforms = framework.list_supported_platforms()
        
        table = Table(title="支持的平台")
        table.add_column("平台名称")
        table.add_column("状态")
        
        for platform in platforms:
            table.add_row(platform, "[green]可用[/green]")
        
        console.print(table)
        await framework.stop()
    
    asyncio.run(_list_platforms())


@app.command()
def monitor(
    accounts: str = typer.Argument(..., help="要监控的账号（用逗号分隔）"),
    limit: int = typer.Option(50, "--limit", "-l", help="每个账号的推文数量限制"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="输出目录")
):
    """监控推特账号"""
    async def _monitor():
        framework = HotStreamFramework()
        
        if not await framework.initialize():
            console.print("[red]框架初始化失败[/red]")
            return
        
        account_list = [account.strip() for account in accounts.split(",")]
        
        try:
            console.print(f"[blue]开始监控账号: {', '.join(account_list)}[/blue]")
            
            # 获取 Twitter 适配器
            adapter = framework.plugin_manager.get_platform_adapter("twitter")
            if not adapter:
                console.print("[red]Twitter 适配器不可用[/red]")
                return
            
            # 初始化适配器 - 从框架配置获取认证信息
            credentials = framework.config.get('platforms', {}).get('twitter', {})
            await adapter.authenticate(credentials)
            
            all_tweets = []
            async for tweet in adapter.monitor_accounts(account_list, limit):
                all_tweets.append(tweet)
                console.print(f"[green]获得推文: @{tweet.author} - {tweet.content[:50]}...[/green]")
            
            console.print(f"[green]监控完成！总共获得 {len(all_tweets)} 条推文[/green]")
            
            # 显示结果表格
            if all_tweets:
                table = Table(title="账号监控结果")
                table.add_column("账号")
                table.add_column("内容预览")
                table.add_column("时间")
                table.add_column("URL")
                
                for tweet in all_tweets[:20]:  # 只显示前20条
                    content_preview = tweet.content[:60] + "..." if len(tweet.content) > 60 else tweet.content
                    table.add_row(
                        f"@{tweet.author}",
                        content_preview,
                        tweet.created_at[:16] if tweet.created_at else "N/A",
                        tweet.url[:50] + "..." if tweet.url and len(tweet.url) > 50 else (tweet.url or "N/A")
                    )
                
                console.print(table)
                
                if len(all_tweets) > 20:
                    console.print(f"[dim]... 还有 {len(all_tweets) - 20} 条推文[/dim]")
        
        except Exception as e:
            console.print(f"[red]监控失败: {e}[/red]")
        
        finally:
            await framework.stop()
    
    asyncio.run(_monitor())


@app.command()
def test_nitter(
    account: str = typer.Argument(..., help="要测试的推特账号"),
    limit: int = typer.Option(5, "--limit", "-l", help="获取推文数量")
):
    """测试 Nitter 数据获取"""
    async def _test_nitter():
        from .plugins.platforms.twitter_adapter import TwitterAdapter
        
        adapter = TwitterAdapter()
        
        try:
            console.print(f"[blue]测试 Nitter 获取 @{account} 的推文...[/blue]")
            
            # 初始化适配器
            if not await adapter.authenticate({}):
                console.print("[red]Nitter 适配器初始化失败[/red]")
                return
            
            tweets = []
            async for tweet in adapter.monitor_accounts([account], limit):
                tweets.append(tweet)
                console.print(f"[green]✓ 获得推文: {tweet.content[:80]}...[/green]")
            
            console.print(f"[green]测试完成！获得 {len(tweets)} 条推文[/green]")
            
            # 显示详细信息
            if tweets:
                table = Table(title=f"@{account} 推文详情")
                table.add_column("内容", width=50)
                table.add_column("时间")
                table.add_column("链接", width=30)
                
                for tweet in tweets:
                    table.add_row(
                        tweet.content[:100] + "..." if len(tweet.content) > 100 else tweet.content,
                        tweet.created_at[:16] if tweet.created_at else "N/A",
                        tweet.url[-30:] if tweet.url else "N/A"
                    )
                
                console.print(table)
        
        except Exception as e:
            console.print(f"[red]测试失败: {e}[/red]")
            import traceback
            console.print(f"[red]详细错误: {traceback.format_exc()}[/red]")
        
        finally:
            await adapter.cleanup()
    
    asyncio.run(_test_nitter())


@app.command()
def add_task(
    task_id: str = typer.Argument(..., help="任务ID"),
    platform: str = typer.Argument(..., help="平台名称"),
    keywords: str = typer.Argument(..., help="搜索关键字（用逗号分隔）"),
    schedule: Optional[str] = typer.Option(None, "--schedule", "-s", help="Cron 表达式"),
    config_file: Optional[str] = typer.Option(None, "--config", "-c", help="配置文件路径")
):
    """添加任务"""
    async def _add_task():
        framework = HotStreamFramework(config_file)
        
        if not await framework.initialize():
            console.print("[red]框架初始化失败[/red]")
            return
        
        keyword_list = [k.strip() for k in keywords.split(",")]
        
        task_config = TaskConfig(
            task_id=task_id,
            name=f"任务_{task_id}",
            platform=platform,
            keywords=keyword_list,
            schedule=schedule
        )
        
        if await framework.add_task(task_config):
            console.print(f"[green]任务添加成功: {task_id}[/green]")
            if schedule:
                console.print(f"调度计划: {schedule}")
        else:
            console.print(f"[red]任务添加失败[/red]")
        
        await framework.stop()
    
    asyncio.run(_add_task())


@app.command()
def info():
    """显示框架信息"""
    async def _info():
        framework = HotStreamFramework()
        
        if not await framework.initialize():
            console.print("[red]框架初始化失败[/red]")
            return
        
        stats = framework.get_framework_stats()
        
        table = Table(title="HotStream 框架信息")
        table.add_column("项目")
        table.add_column("值")
        
        table.add_row("运行状态", "[green]运行中[/green]" if stats["running"] else "[red]已停止[/red]")
        table.add_row("任务总数", str(stats["total_tasks"]))
        table.add_row("支持平台", str(stats["supported_platforms"]))
        table.add_row("加载插件", str(stats["loaded_plugins"]))
        
        console.print(table)
        await framework.stop()
    
    asyncio.run(_info())


@app.command()
def create_task(
    task_id: str = typer.Argument(..., help="任务ID"),
    task_type: str = typer.Argument(..., help="任务类型 (search/monitor)"),
    platform: str = typer.Argument(..., help="平台名称"),
    keywords: Optional[str] = typer.Option(None, "--keywords", "-k", help="搜索关键字（用逗号分隔）"),
    accounts: Optional[str] = typer.Option(None, "--accounts", "-a", help="监控账号（用逗号分隔）"),
    limit: int = typer.Option(50, "--limit", "-l", help="数据限制"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="任务名称"),
    priority: int = typer.Option(5, "--priority", "-p", help="优先级 (1=最高, 10=最低, 5=普通)"),
    immediate: bool = typer.Option(False, "--immediate", help="立即执行"),
    storage_type: str = typer.Option("mongodb", "--storage", help="存储类型 (mongodb/json)")
):
    """创建数据库任务"""
    async def _create_task():
        framework = HotStreamFramework()
        
        if not await framework.initialize():
            console.print("[red]框架初始化失败[/red]")
            return
        
        task_name = name or f"{task_type}_{platform}_{task_id}"
        
        try:
            if task_type == "search":
                if not keywords:
                    console.print("[red]搜索任务需要指定关键字[/red]")
                    return
                
                keyword_list = [k.strip() for k in keywords.split(",")]
                success = await framework.create_search_task(
                    task_id=task_id,
                    name=task_name,
                    platform=platform,
                    keywords=keyword_list,
                    priority=priority,
                    immediate=immediate,
                    storage_type=storage_type,
                    limit=limit
                )
                
            elif task_type == "monitor":
                if not accounts:
                    console.print("[red]监控任务需要指定账号[/red]")
                    return
                
                account_list = [a.strip() for a in accounts.split(",")]
                success = await framework.create_monitor_task(
                    task_id=task_id,
                    name=task_name,
                    platform=platform,
                    accounts=account_list,
                    priority=priority,
                    immediate=immediate,
                    storage_type=storage_type,
                    limit=limit
                )
                
            else:
                console.print(f"[red]不支持的任务类型: {task_type}[/red]")
                return
            
            if success:
                console.print(f"[green]任务创建成功: {task_id}[/green]")
                console.print(f"类型: {task_type}")
                console.print(f"平台: {platform}")
                if keywords:
                    console.print(f"关键字: {keywords}")
                if accounts:
                    console.print(f"账号: {accounts}")
                console.print(f"优先级: {priority} {'(高优先级)' if priority <= 3 else '(普通)' if priority <= 7 else '(低优先级)'}")
                console.print(f"立即执行: {'是' if immediate else '否'}")
                console.print(f"存储方式: {storage_type}")
                console.print(f"数据限制: {limit}")
            else:
                console.print(f"[red]任务创建失败: {task_id}[/red]")
        
        except Exception as e:
            console.print(f"[red]创建任务时出错: {e}[/red]")
        
        finally:
            await framework.stop()
    
    asyncio.run(_create_task())


@app.command()
def task_stats():
    """显示任务统计信息"""
    async def _task_stats():
        framework = HotStreamFramework()
        
        if not await framework.initialize():
            console.print("[red]框架初始化失败[/red]")
            return
        
        try:
            stats = await framework.get_task_stats()
            
            table = Table(title="任务统计信息")
            table.add_column("项目")
            table.add_column("值")
            
            table.add_row("调度器运行状态", "[green]运行中[/green]" if stats.get("scheduler_running") else "[red]已停止[/red]")
            table.add_row("正在处理任务", str(stats.get("processing_tasks", 0)))
            table.add_row("最大并发任务", str(stats.get("max_concurrent_tasks", 0)))
            table.add_row("总任务数", str(stats.get("total_count", 0)))
            
            # 显示按状态统计
            by_status = stats.get("by_status", {})
            if by_status:
                console.print("\n[bold]按状态统计:[/bold]")
                status_table = Table()
                status_table.add_column("状态")
                status_table.add_column("数量")
                
                status_names = {0: "待处理", 1: "运行中", 2: "已完成", 3: "失败", 4: "已取消"}
                for status_code, count in by_status.items():
                    status_name = status_names.get(status_code, f"状态{status_code}")
                    status_table.add_row(status_name, str(count))
                
                console.print(status_table)
            
            # 显示按平台统计
            platform_stats = stats.get("platform_stats", {})
            if platform_stats:
                console.print("\n[bold]按平台统计:[/bold]")
                platform_table = Table()
                platform_table.add_column("平台")
                platform_table.add_column("数量")
                
                for platform, count in platform_stats.items():
                    platform_table.add_row(platform, str(count))
                
                console.print(platform_table)
            
            console.print(table)
        
        except Exception as e:
            console.print(f"[red]获取统计信息失败: {e}[/red]")
        
        finally:
            await framework.stop()
    
    asyncio.run(_task_stats())


@app.command()
def start_daemon():
    """启动数据处理守护进程"""
    async def _start_daemon():
        framework = HotStreamFramework()
        
        console.print("[blue]启动HotStream数据处理守护进程...[/blue]")
        
        try:
            if not await framework.initialize():
                console.print("[red]框架初始化失败[/red]")
                return
            
            # 启动调度器
            await framework.scheduler.start()
            console.print("[green]数据处理守护进程已启动[/green]")
            console.print("按 Ctrl+C 停止...")
            
            # 保持运行，显示实时状态
            try:
                while True:
                    await asyncio.sleep(30)  # 每30秒显示一次状态
                    
                    stats = await framework.get_task_stats()
                    processing = stats.get("processing_tasks", 0)
                    total = stats.get("total_count", 0)
                    
                    if processing > 0:
                        console.print(f"[yellow]正在处理 {processing} 个任务，总任务数: {total}[/yellow]")
            
            except KeyboardInterrupt:
                console.print("\n[yellow]收到停止信号...[/yellow]")
        
        except Exception as e:
            console.print(f"[red]守护进程启动失败: {e}[/red]")
        
        finally:
            console.print("[blue]正在停止守护进程...[/blue]")
            await framework.stop()
            console.print("[green]守护进程已停止[/green]")
    
    asyncio.run(_start_daemon())


@app.command()
def query_data(
    task_id: str = typer.Argument(..., help="任务ID"),
    limit: int = typer.Option(50, "--limit", "-l", help="查询数量限制"),
    format: str = typer.Option("table", "--format", "-f", help="输出格式 (table/json)")
):
    """根据任务ID查询采集的数据"""
    async def _query():
        try:
            from .plugins.storages.mongo_storage import MongoStorageAdapter
            from .config.config_manager import ConfigManager
            
            # 加载配置
            config_manager = ConfigManager()
            config = config_manager.load_config()
            
            # 初始化存储适配器
            mongo_config = config.get('mongodb', {})
            storage = MongoStorageAdapter(
                mongo_uri=mongo_config.get('uri', 'mongodb://localhost:27017'),
                db_name=mongo_config.get('database', 'hotstream')
            )
            
            if not await storage.initialize():
                console.print("[red]存储适配器初始化失败[/red]")
                return
            
            # 查询数据
            filters = {"task_id": task_id}
            
            # 直接使用MongoDB查询
            cursor = storage.collection.find(filters).limit(limit).sort("created_at", -1)
            items = []
            async for doc in cursor:
                items.append(doc)
            
            if not items:
                console.print(f"[yellow]未找到任务 {task_id} 的数据[/yellow]")
                return
            
            if format == "json":
                import json
                # 处理MongoDB的ObjectId和datetime
                for item in items:
                    if '_id' in item:
                        item['_id'] = str(item['_id'])
                    for key, value in item.items():
                        if hasattr(value, 'isoformat'):
                            item[key] = value.isoformat()
                
                console.print(json.dumps(items, ensure_ascii=False, indent=2))
            else:
                # 表格格式
                table = Table(title=f"任务 {task_id} 的数据")
                table.add_column("ID", style="cyan")
                table.add_column("平台", style="magenta")
                table.add_column("作者", style="green")
                table.add_column("内容", style="yellow", max_width=50)
                table.add_column("创建时间", style="blue")
                
                for item in items:
                    content = item.get('content', '')[:100] + "..." if len(item.get('content', '')) > 100 else item.get('content', '')
                    table.add_row(
                        item.get('id', '')[:12] + "...",
                        item.get('platform', ''),
                        item.get('author', ''),
                        content,
                        str(item.get('created_at', ''))[:19]
                    )
                
                console.print(table)
                console.print(f"\n[green]共找到 {len(items)} 条数据[/green]")
            
            await storage.close()
            
        except Exception as e:
            console.print(f"[red]查询数据失败: {e}[/red]")
    
    asyncio.run(_query())


if __name__ == "__main__":
    app()