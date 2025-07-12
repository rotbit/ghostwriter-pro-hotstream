#!/bin/bash

# GhostWriter Pro HotStream - 一键卸载脚本
# Author: HotStream Team
# Description: 自动卸载 HotStream 框架和清理相关文件

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# 检查操作系统
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    elif [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "msys" ]]; then
        echo "windows"
    else
        echo "unknown"
    fi
}

# 停止和删除系统服务
remove_service() {
    local os=$(detect_os)
    if [ "$os" = "linux" ] && [ -f "/etc/systemd/system/hotstream.service" ]; then
        log_info "停止并删除系统服务..."
        
        # 停止服务
        if systemctl is-active --quiet hotstream.service; then
            sudo systemctl stop hotstream.service
            log_success "服务已停止"
        fi
        
        # 禁用服务
        if systemctl is-enabled --quiet hotstream.service; then
            sudo systemctl disable hotstream.service
            log_success "服务已禁用"
        fi
        
        # 删除服务文件
        sudo rm -f /etc/systemd/system/hotstream.service
        sudo systemctl daemon-reload
        log_success "系统服务已删除"
    else
        log_info "未找到系统服务"
    fi
}

# 停止 Docker 容器
stop_docker_containers() {
    if command_exists docker; then
        log_info "停止 Docker 容器..."
        
        # 停止 HotStream 相关容器
        local containers=$(docker ps -q --filter "ancestor=ghostwriter-pro-hotstream")
        if [ ! -z "$containers" ]; then
            docker stop $containers
            docker rm $containers
            log_success "Docker 容器已停止并删除"
        fi
        
        # 使用 docker-compose 停止（如果存在）
        if [ -f "docker-compose.yml" ]; then
            if command_exists docker-compose; then
                docker-compose down
            elif docker compose version >/dev/null 2>&1; then
                docker compose down
            fi
            log_success "Docker Compose 容器已停止"
        fi
    else
        log_info "Docker 未安装，跳过容器清理"
    fi
}

# 删除 Docker 镜像
remove_docker_images() {
    if command_exists docker && [ "$REMOVE_DOCKER_IMAGES" = "yes" ]; then
        log_info "删除 Docker 镜像..."
        
        # 删除 HotStream 镜像
        local images=$(docker images -q ghostwriter-pro-hotstream)
        if [ ! -z "$images" ]; then
            docker rmi $images
            log_success "Docker 镜像已删除"
        fi
        
        # 清理悬挂镜像
        docker image prune -f
        log_success "悬挂镜像已清理"
    fi
}

# 卸载 Python 包
uninstall_python_package() {
    log_info "卸载 Python 包..."
    
    # 检查并激活虚拟环境
    if [ -d "venv" ]; then
        source venv/bin/activate
        log_info "已激活虚拟环境"
        
        # 卸载 HotStream 包
        if pip show hotstream >/dev/null 2>&1; then
            pip uninstall -y hotstream
            log_success "HotStream 包已卸载"
        fi
        
        # 卸载其他依赖（可选）
        if [ "$REMOVE_DEPENDENCIES" = "yes" ] && [ -f "requirements.txt" ]; then
            pip uninstall -y -r requirements.txt
            log_success "依赖包已卸载"
        fi
        
        deactivate
    else
        log_warning "虚拟环境不存在"
    fi
}

# 删除虚拟环境
remove_venv() {
    if [ -d "venv" ] && [ "$REMOVE_VENV" = "yes" ]; then
        log_info "删除虚拟环境..."
        rm -rf venv
        log_success "虚拟环境已删除"
    fi
}

# 清理数据文件
cleanup_data() {
    if [ "$CLEANUP_DATA" = "yes" ]; then
        log_info "清理数据文件..."
        
        # 清理输出目录
        if [ -d "output" ]; then
            rm -rf output/*
            log_success "输出目录已清理"
        fi
        
        # 清理日志目录
        if [ -d "logs" ]; then
            rm -rf logs/*
            log_success "日志目录已清理"
        fi
        
        # 清理缓存目录
        if [ -d "__pycache__" ]; then
            find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
            log_success "Python 缓存已清理"
        fi
        
        # 清理 .pyc 文件
        find . -name "*.pyc" -type f -delete 2>/dev/null || true
        log_success ".pyc 文件已清理"
    fi
}

# 删除配置文件
remove_config() {
    if [ "$REMOVE_CONFIG" = "yes" ]; then
        log_info "删除配置文件..."
        
        # 删除配置目录
        if [ -d "configs" ]; then
            rm -rf configs
            log_success "配置目录已删除"
        fi
        
        # 删除用户配置目录
        if [ -d "$HOME/.hotstream" ]; then
            rm -rf "$HOME/.hotstream"
            log_success "用户配置目录已删除"
        fi
    fi
}

# 删除 Playwright 浏览器
remove_playwright_browsers() {
    if [ "$REMOVE_BROWSERS" = "yes" ]; then
        log_info "删除 Playwright 浏览器..."
        
        # 检查并激活虚拟环境
        if [ -d "venv" ]; then
            source venv/bin/activate
            
            # 卸载 Playwright 浏览器
            if command_exists playwright; then
                playwright uninstall
                log_success "Playwright 浏览器已删除"
            fi
            
            deactivate
        fi
        
        # 删除浏览器缓存目录
        if [ -d "$HOME/.cache/ms-playwright" ]; then
            rm -rf "$HOME/.cache/ms-playwright"
            log_success "浏览器缓存已删除"
        fi
    fi
}

# 删除安装脚本和相关文件
remove_scripts() {
    if [ "$REMOVE_SCRIPTS" = "yes" ]; then
        log_info "删除安装脚本..."
        
        # 删除 Docker 相关文件
        [ -f "Dockerfile" ] && rm -f Dockerfile && log_success "Dockerfile 已删除"
        [ -f "docker-compose.yml" ] && rm -f docker-compose.yml && log_success "docker-compose.yml 已删除"
        [ -f ".dockerignore" ] && rm -f .dockerignore && log_success ".dockerignore 已删除"
        
        # 删除脚本文件（最后删除，因为当前正在执行）
        echo "install.sh 和 uninstall.sh 将在脚本执行完成后删除"
    fi
}

# 询问用户选择
ask_user_preferences() {
    echo -e "${YELLOW}请选择要执行的卸载操作:${NC}"
    
    read -p "是否删除 Docker 镜像? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        REMOVE_DOCKER_IMAGES="yes"
    else
        REMOVE_DOCKER_IMAGES="no"
    fi
    
    read -p "是否删除虚拟环境? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        REMOVE_VENV="yes"
    else
        REMOVE_VENV="no"
    fi
    
    read -p "是否卸载 Python 依赖包? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        REMOVE_DEPENDENCIES="yes"
    else
        REMOVE_DEPENDENCIES="no"
    fi
    
    read -p "是否清理数据文件 (输出、日志等)? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        CLEANUP_DATA="yes"
    else
        CLEANUP_DATA="no"
    fi
    
    read -p "是否删除配置文件? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        REMOVE_CONFIG="yes"
    else
        REMOVE_CONFIG="no"
    fi
    
    read -p "是否删除 Playwright 浏览器? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        REMOVE_BROWSERS="yes"
    else
        REMOVE_BROWSERS="no"
    fi
    
    read -p "是否删除安装脚本和 Docker 文件? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        REMOVE_SCRIPTS="yes"
    else
        REMOVE_SCRIPTS="no"
    fi
}

# 主卸载函数
main() {
    echo -e "${RED}"
    echo "=========================================="
    echo "  GhostWriter Pro HotStream 一键卸载"
    echo "=========================================="
    echo -e "${NC}"
    
    # 检查是否在项目根目录
    if [ ! -d "hotstream" ] && [ ! -f "install.sh" ]; then
        log_error "请在项目根目录运行此脚本"
        exit 1
    fi
    
    # 确认卸载
    echo -e "${YELLOW}警告: 此操作将卸载 HotStream 及相关组件${NC}"
    read -p "确定要继续吗? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "卸载已取消"
        exit 0
    fi
    
    # 询问用户偏好
    ask_user_preferences
    
    echo -e "${BLUE}开始卸载...${NC}"
    
    # 执行卸载步骤
    remove_service
    stop_docker_containers
    remove_docker_images
    uninstall_python_package
    remove_playwright_browsers
    remove_venv
    cleanup_data
    remove_config
    remove_scripts
    
    echo -e "${GREEN}"
    echo "=========================================="
    echo "           卸载完成！"
    echo "=========================================="
    echo -e "${NC}"
    
    log_success "HotStream 已成功卸载"
    
    if [ "$REMOVE_SCRIPTS" = "yes" ]; then
        log_info "删除安装和卸载脚本..."
        # 使用 at 命令延迟删除脚本文件（如果可用）
        if command_exists at; then
            echo "rm -f install.sh uninstall.sh" | at now + 1 minute 2>/dev/null || {
                log_warning "无法自动删除脚本文件，请手动删除 install.sh 和 uninstall.sh"
            }
        else
            log_warning "请手动删除 install.sh 和 uninstall.sh 文件"
        fi
    fi
    
    echo -e "${BLUE}感谢使用 GhostWriter Pro HotStream！${NC}"
}

# 错误处理
trap 'log_error "卸载过程中出现错误，请检查上述输出"; exit 1' ERR

# 运行主函数
main "$@"