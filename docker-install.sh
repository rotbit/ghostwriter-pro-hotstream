#!/bin/bash

# GhostWriter Pro HotStream - Docker 快速安装脚本
# 专门用于纯 Docker 部署，无需本地 Python 环境

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查命令是否存在
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 检查 Docker 是否安装
check_docker() {
    if ! command_exists docker; then
        log_error "Docker 未安装"
        log_info "请先安装 Docker Desktop 或 Docker Engine"
        log_info "macOS: https://www.docker.com/products/docker-desktop"
        log_info "Linux: curl -fsSL https://get.docker.com | sh"
        exit 1
    fi
    
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker 守护进程未运行"
        log_info "请启动 Docker Desktop 或 Docker 守护进程"
        exit 1
    fi
    
    log_success "Docker 环境验证通过"
}

# 检查 Docker Compose
check_docker_compose() {
    if command_exists docker-compose; then
        log_success "Docker Compose 可用 (独立版本)"
        COMPOSE_CMD="docker-compose"
    elif docker compose version >/dev/null 2>&1; then
        log_success "Docker Compose 可用 (插件版本)"
        COMPOSE_CMD="docker compose"
    else
        log_error "Docker Compose 未安装"
        log_info "请安装 Docker Compose"
        exit 1
    fi
}

# 创建配置文件
create_config() {
    log_info "创建配置文件..."
    
    mkdir -p configs output logs
    
    if [ ! -f "configs/hotstream.yaml" ]; then
        cat > configs/hotstream.yaml << EOF
framework:
  debug: false
  log_level: "INFO"
  
platforms:
  twitter:
    enabled: true
    rate_limit:
      requests_per_minute: 100
  
storage:
  default_type: "json"
  output_dir: "output"
  
crawler:
  timeout: 30
  retry_count: 3
EOF
        log_success "默认配置文件创建完成"
    else
        log_warning "配置文件已存在"
    fi
}

# 构建 Docker 镜像
build_image() {
    log_info "构建 Docker 镜像..."
    
    if docker build -t ghostwriter-pro-hotstream:latest .; then
        log_success "Docker 镜像构建完成"
    else
        log_error "Docker 镜像构建失败"
        exit 1
    fi
}

# 启动服务
start_services() {
    log_info "启动 Docker 服务..."
    
    if $COMPOSE_CMD up -d; then
        log_success "服务启动成功"
    else
        log_error "服务启动失败"
        exit 1
    fi
}

# 显示状态
show_status() {
    echo -e "${GREEN}"
    echo "=========================================="
    echo "        Docker 部署完成！"
    echo "=========================================="
    echo -e "${NC}"
    
    echo -e "${BLUE}服务状态:${NC}"
    $COMPOSE_CMD ps
    
    echo ""
    echo -e "${BLUE}常用命令:${NC}"
    echo "查看日志: $COMPOSE_CMD logs -f hotstream"
    echo "执行命令: $COMPOSE_CMD exec hotstream python -m hotstream.cli --help"
    echo "搜索数据: $COMPOSE_CMD exec hotstream python -m hotstream.cli search twitter \"AI\" --limit 10"
    echo "停止服务: $COMPOSE_CMD down"
    echo "重启服务: $COMPOSE_CMD restart hotstream"
    
    echo ""
    echo -e "${BLUE}Web 界面:${NC}"
    echo "如果启用了 Web 界面，请访问: http://localhost:8000"
    
    echo ""
    echo -e "${YELLOW}注意事项:${NC}"
    echo "- 配置文件位于: configs/hotstream.yaml"
    echo "- 输出文件位于: output/"
    echo "- 日志文件位于: logs/"
}

# 主函数
main() {
    echo -e "${GREEN}"
    echo "=========================================="
    echo "   GhostWriter Pro HotStream Docker 安装"
    echo "=========================================="
    echo -e "${NC}"
    
    # 检查是否在项目根目录
    if [ ! -f "Dockerfile" ] || [ ! -f "docker-compose.yml" ]; then
        log_error "请在项目根目录运行此脚本"
        exit 1
    fi
    
    log_info "开始 Docker 快速部署..."
    
    # 检查 Docker 环境
    check_docker
    check_docker_compose
    
    # 创建配置
    create_config
    
    # 构建和启动
    build_image
    start_services
    
    # 显示结果
    show_status
}

# 错误处理
trap 'log_error "安装过程中出现错误"; exit 1' ERR

# 运行主函数
main "$@"