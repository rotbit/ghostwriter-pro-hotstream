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
        console.print(f"API 地址: http://{host}:{port}")
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


if __name__ == "__main__":
    app()