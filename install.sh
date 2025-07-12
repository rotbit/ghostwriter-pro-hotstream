#!/bin/bash

# GhostWriter Pro HotStream - 一键安装脚本
# Author: HotStream Team
# Description: 自动安装 HotStream 框架和依赖

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

# 安装 Python 依赖管理器
install_python() {
    local os=$(detect_os)
    
    if ! command_exists python3; then
        log_info "正在安装 Python3..."
        case $os in
            "linux")
                if command_exists apt-get; then
                    sudo apt-get update
                    sudo apt-get install -y python3 python3-pip python3-venv
                elif command_exists yum; then
                    sudo yum install -y python3 python3-pip
                elif command_exists dnf; then
                    sudo dnf install -y python3 python3-pip
                else
                    log_error "不支持的 Linux 发行版，请手动安装 Python3"
                    exit 1
                fi
                ;;
            "macos")
                if command_exists brew; then
                    brew install python3
                else
                    log_error "请先安装 Homebrew 或手动安装 Python3"
                    exit 1
                fi
                ;;
            *)
                log_error "不支持的操作系统，请手动安装 Python3"
                exit 1
                ;;
        esac
    else
        log_success "Python3 已安装"
    fi
}

# 安装 Docker
install_docker() {
    local os=$(detect_os)
    
    if ! command_exists docker; then
        log_info "正在安装 Docker..."
        case $os in
            "linux")
                curl -fsSL https://get.docker.com -o get-docker.sh
                sudo sh get-docker.sh
                sudo usermod -aG docker $USER
                rm get-docker.sh
                ;;
            "macos")
                log_warning "请手动下载并安装 Docker Desktop for Mac"
                log_info "下载地址: https://www.docker.com/products/docker-desktop"
                ;;
            *)
                log_error "请手动安装 Docker"
                exit 1
                ;;
        esac
    else
        log_success "Docker 已安装"
    fi
}

# 安装 Docker Compose
install_docker_compose() {
    if ! command_exists docker-compose && ! docker compose version >/dev/null 2>&1; then
        log_info "正在安装 Docker Compose..."
        local os=$(detect_os)
        case $os in
            "linux")
                sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
                sudo chmod +x /usr/local/bin/docker-compose
                ;;
            "macos")
                log_info "Docker Compose 通常与 Docker Desktop 一起安装"
                ;;
        esac
    else
        log_success "Docker Compose 已安装"
    fi
}

# 创建 Python 虚拟环境
create_venv() {
    log_info "创建 Python 虚拟环境..."
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        log_success "虚拟环境创建成功"
    else
        log_warning "虚拟环境已存在"
    fi
    
    # 激活虚拟环境
    source venv/bin/activate
    log_info "已激活虚拟环境"
}

# 安装 Python 依赖
install_dependencies() {
    log_info "安装 Python 依赖..."
    
    # 升级 pip
    pip install --upgrade pip
    
    # 安装项目依赖
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt
        log_success "依赖安装完成"
    else
        log_error "requirements.txt 文件不存在"
        exit 1
    fi
    
    # 安装 Playwright 浏览器
    log_info "安装 Playwright 浏览器..."
    playwright install
    log_success "Playwright 浏览器安装完成"
}

# 安装项目
install_project() {
    log_info "安装 HotStream 项目..."
    pip install -e .
    log_success "项目安装完成"
}

# 创建配置文件
create_config() {
    log_info "创建配置文件..."
    
    # 创建配置目录
    mkdir -p configs
    mkdir -p output
    mkdir -p logs
    
    # 创建默认配置文件（如果不存在）
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
build_docker_image() {
    if [ "$INSTALL_DOCKER" = "yes" ]; then
        log_info "构建 Docker 镜像..."
        docker build -t ghostwriter-pro-hotstream:latest .
        log_success "Docker 镜像构建完成"
    fi
}

# 创建服务文件（可选）
create_service() {
    local os=$(detect_os)
    if [ "$os" = "linux" ] && [ "$CREATE_SERVICE" = "yes" ]; then
        log_info "创建系统服务..."
        
        sudo tee /etc/systemd/system/hotstream.service > /dev/null << EOF
[Unit]
Description=GhostWriter Pro HotStream
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
Environment=PATH=$(pwd)/venv/bin
ExecStart=$(pwd)/venv/bin/python -m hotstream.cli start
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
        
        sudo systemctl daemon-reload
        sudo systemctl enable hotstream.service
        log_success "系统服务创建完成"
        log_info "使用 'sudo systemctl start hotstream' 启动服务"
    fi
}

# 主安装函数
main() {
    echo -e "${GREEN}"
    echo "=========================================="
    echo "  GhostWriter Pro HotStream 一键安装"
    echo "=========================================="
    echo -e "${NC}"
    
    # 检查是否在项目根目录
    if [ ! -f "requirements.txt" ] || [ ! -d "hotstream" ]; then
        log_error "请在项目根目录运行此脚本"
        exit 1
    fi
    
    # 安装选项
    read -p "是否安装 Docker 支持? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        INSTALL_DOCKER="yes"
    else
        INSTALL_DOCKER="no"
    fi
    
    read -p "是否创建系统服务? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        CREATE_SERVICE="yes"
    else
        CREATE_SERVICE="no"
    fi
    
    # 开始安装
    log_info "开始安装 HotStream..."
    
    # 安装 Python
    install_python
    
    # 安装 Docker（如果选择）
    if [ "$INSTALL_DOCKER" = "yes" ]; then
        install_docker
        install_docker_compose
    fi
    
    # 创建虚拟环境和安装依赖
    create_venv
    install_dependencies
    install_project
    
    # 创建配置
    create_config
    
    # 构建 Docker 镜像（如果选择）
    build_docker_image
    
    # 创建服务（如果选择）
    create_service
    
    echo -e "${GREEN}"
    echo "=========================================="
    echo "           安装完成！"
    echo "=========================================="
    echo -e "${NC}"
    
    echo -e "${BLUE}使用方法:${NC}"
    echo "1. 激活虚拟环境: source venv/bin/activate"
    echo "2. 启动框架: python -m hotstream.cli start"
    echo "3. 搜索数据: python -m hotstream.cli search twitter \"AI,机器学习\" --limit 50"
    echo "4. 查看帮助: python -m hotstream.cli --help"
    
    if [ "$INSTALL_DOCKER" = "yes" ]; then
        echo -e "${BLUE}Docker 使用:${NC}"
        echo "1. 直接运行: docker run -it ghostwriter-pro-hotstream:latest"
        echo "2. 使用 compose: docker-compose up -d"
    fi
    
    echo -e "${YELLOW}注意事项:${NC}"
    echo "- 请根据需要修改 configs/hotstream.yaml 配置文件"
    echo "- 第一次运行可能需要下载浏览器，请耐心等待"
    echo "- 如有问题请查看 logs/ 目录下的日志文件"
}

# 错误处理
trap 'log_error "安装过程中出现错误，请检查上述输出"; exit 1' ERR

# 运行主函数
main "$@"