#!/bin/bash

# GhostWriter Pro HotStream - Docker 安装脚本
# 纯 Docker 模式部署

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

# 修复 Docker 凭据配置问题
fix_docker_credentials() {
    local docker_config="$HOME/.docker/config.json"
    
    if [ -f "$docker_config" ]; then
        log_info "检测到 Docker 凭据配置问题，正在修复..."
        
        # 备份原配置
        cp "$docker_config" "${docker_config}.backup.$(date +%s)" 2>/dev/null || true
        
        # 检查是否有 credsStore 问题
        if grep -q '"credsStore".*"desktop"' "$docker_config" 2>/dev/null; then
            log_info "移除有问题的 credsStore 配置..."
            
            # 创建修复后的配置
            python3 -c "
import json
import sys
try:
    with open('$docker_config', 'r') as f:
        config = json.load(f)
    
    # 移除有问题的 credsStore
    if 'credsStore' in config:
        del config['credsStore']
    
    with open('$docker_config', 'w') as f:
        json.dump(config, f, indent=2)
    
    print('Docker 配置已修复')
except Exception as e:
    print(f'修复失败: {e}', file=sys.stderr)
    sys.exit(1)
"
            if [ $? -eq 0 ]; then
                log_success "Docker 凭据配置已修复"
            else
                log_warning "自动修复失败，请手动检查 Docker 配置"
            fi
        fi
    fi
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

# 检查并安装 Docker
check_install_docker() {
    if ! command_exists docker; then
        local os=$(detect_os)
        log_info "Docker 未安装，正在安装..."
        
        case $os in
            "linux")
                if curl -fsSL https://get.docker.com -o get-docker.sh; then
                    if sudo sh get-docker.sh; then
                        sudo usermod -aG docker $USER
                        log_success "Docker 安装完成"
                        log_warning "请重新登录或运行 'newgrp docker' 以使组权限生效"
                    else
                        log_error "Docker 安装失败"
                        exit 1
                    fi
                    rm -f get-docker.sh
                else
                    log_error "无法下载 Docker 安装脚本"
                    exit 1
                fi
                ;;
            "macos")
                log_error "请先安装 Docker Desktop for Mac"
                log_info "下载地址: https://www.docker.com/products/docker-desktop"
                exit 1
                ;;
            *)
                log_error "不支持的操作系统，请手动安装 Docker"
                exit 1
                ;;
        esac
    else
        log_success "Docker 已安装"
    fi
    
    # 验证 Docker 是否可用
    if ! docker info >/dev/null 2>&1; then
        log_warning "Docker 守护进程访问失败，尝试修复..."
        fix_docker_credentials
        
        if ! docker info >/dev/null 2>&1; then
            log_error "Docker 无法正常工作"
            log_info "请检查 Docker 是否正在运行"
            exit 1
        fi
    fi
    
    log_success "Docker 环境验证通过"
}

# 创建配置文件
create_config() {
    log_info "创建配置文件..."
    
    mkdir -p configs output logs
    
    if [ ! -f "configs/hotstream.yaml" ]; then
        cat > configs/hotstream.yaml << 'EOF'
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

# 清理现有容器和镜像
cleanup_docker() {
    log_info "清理现有 Docker 环境..."
    
    # 停止并删除 HotStream 相关容器
    local existing_containers=$(docker ps -aq --filter "name=hotstream" 2>/dev/null)
    if [ ! -z "$existing_containers" ]; then
        log_info "停止并删除现有容器..."
        docker stop $existing_containers 2>/dev/null || true
        docker rm $existing_containers 2>/dev/null || true
    fi
    
    # 删除现有镜像
    local existing_images=$(docker images -q ghostwriter-pro-hotstream 2>/dev/null)
    if [ ! -z "$existing_images" ]; then
        log_info "删除现有镜像..."
        docker rmi $existing_images 2>/dev/null || true
    fi
    
    # 清理悬挂的镜像
    docker image prune -f >/dev/null 2>&1 || true
    
    log_success "Docker 环境清理完成"
}

# 构建 Docker 镜像
build_docker_image() {
    log_info "构建 Docker 镜像..."
    
    if docker build -t ghostwriter-pro-hotstream:latest .; then
        log_success "Docker 镜像构建完成"
    else
        log_error "Docker 镜像构建失败"
        log_warning "请检查 Dockerfile 和网络连接"
        exit 1
    fi
}

# 启动 Docker 容器
start_docker_container() {
    log_info "启动 Docker 容器..."
    
    # 创建必要的目录（如果不存在）
    mkdir -p output logs configs
    
    # 启动容器
    if docker run -d \
        --name hotstream-app \
        --init \
        --ipc=host \
        -p 8000:8000 \
        -v "$(pwd)/output:/app/output" \
        -v "$(pwd)/logs:/app/logs" \
        -v "$(pwd)/configs:/app/configs" \
        -e HOTSTREAM_ENV=production \
        -e HOTSTREAM_LOG_LEVEL=INFO \
        --restart unless-stopped \
        ghostwriter-pro-hotstream:latest; then
        
        log_success "Docker 容器启动成功"
        
        # 等待容器完全启动
        log_info "等待容器完全启动..."
        sleep 5
        
        # 显示容器状态
        log_info "容器状态:"
        docker ps --filter "name=hotstream-app"
        
        # 显示容器日志（最后10行）
        log_info "容器启动日志:"
        docker logs --tail 10 hotstream-app
        
    else
        log_error "Docker 容器启动失败"
        log_info "请检查 Docker 配置和镜像"
        exit 1
    fi
}

# 主函数
main() {
    echo -e "${GREEN}"
    echo "=========================================="
    echo "  GhostWriter Pro HotStream Docker 部署"
    echo "=========================================="
    echo -e "${NC}"
    
    # 检查是否在项目根目录
    if [ ! -f "Dockerfile" ] || [ ! -d "hotstream" ]; then
        log_error "请在项目根目录运行此脚本"
        exit 1
    fi
    
    log_info "开始 Docker 自动化部署..."
    
    # 检查并安装 Docker
    check_install_docker
    
    # 创建配置文件
    create_config
    
    # Docker 完整部署流程
    cleanup_docker
    build_docker_image
    start_docker_container
    
    echo -e "${GREEN}"
    echo "=========================================="
    echo "           部署完成！"
    echo "=========================================="
    echo -e "${NC}"
    
    echo -e "${BLUE}Docker 使用方法:${NC}"
    echo "1. 查看容器状态: docker ps"
    echo "2. 查看日志: docker logs -f hotstream-app"
    echo "3. 执行命令: docker exec -it hotstream-app python -m hotstream.cli --help"
    echo "4. 搜索数据: docker exec -it hotstream-app python -m hotstream.cli search twitter \"AI,机器学习\" --limit 50"
    echo "5. 停止容器: docker stop hotstream-app"
    echo "6. 重启容器: docker restart hotstream-app"
    echo "7. 删除容器: docker rm -f hotstream-app"
    
    echo ""
    echo -e "${BLUE}Web 界面:${NC}"
    echo "如果启用了 Web 界面，请访问: http://localhost:8000"
    
    echo ""
    echo -e "${YELLOW}注意事项:${NC}"
    echo "- 配置文件位于: configs/hotstream.yaml"
    echo "- 输出文件位于: output/"
    echo "- 日志文件位于: logs/"
    echo "- 容器会自动重启，如需永久停止请使用: docker stop hotstream-app"
}

# 错误处理
handle_error() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "命令执行失败 (退出码: $exit_code)"
        log_warning "部署过程中出现错误，请检查上述输出"
        exit 1
    fi
}

# 设置错误处理
trap 'handle_error' ERR

# 运行主函数
main "$@"