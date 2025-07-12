#!/bin/bash

# GhostWriter Pro HotStream - 本地开发测试启动脚本

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

# 检查Python环境
check_python() {
    if ! command_exists python3; then
        log_error "Python3 未安装"
        exit 1
    fi
    
    local python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    if python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
        log_success "Python $python_version 版本检查通过"
    else
        log_error "Python 版本过低: $python_version < 3.8"
        exit 1
    fi
}

# 设置虚拟环境
setup_venv() {
    if [ ! -d "venv" ]; then
        log_info "创建Python虚拟环境..."
        python3 -m venv venv
        log_success "虚拟环境创建完成"
    fi
    
    log_info "激活虚拟环境..."
    source venv/bin/activate
    
    # 检查是否需要安装依赖
    if ! python -c "import playwright" 2>/dev/null; then
        log_info "安装项目依赖..."
        pip install --upgrade pip
        pip install -r requirements.txt
        log_success "依赖安装完成"
        
        log_info "安装Playwright浏览器..."
        playwright install chromium
        log_success "Playwright浏览器安装完成"
    fi
    
    # 安装项目本身
    if ! python -c "import hotstream" 2>/dev/null; then
        log_info "安装HotStream项目..."
        pip install -e .
        log_success "项目安装完成"
    fi
}

# 创建开发配置
create_dev_config() {
    log_info "创建开发配置..."
    
    mkdir -p configs output logs
    
    # 创建开发配置文件
    cat > configs/hotstream-dev.yaml << 'EOF'
framework:
  debug: true
  log_level: "DEBUG"
  
platforms:
  twitter:
    enabled: true
    nitter_instance: "https://nitter.poast.org"
    rate_limit:
      requests_per_minute: 30
      delay_between_requests: 2
    monitored_accounts:
      - "elonmusk"
      - "openai"
      - "github"
  
storage:
  default_type: "json"
  output_dir: "output"
  
crawler:
  timeout: 30
  retry_count: 3
  headless: true
  
scheduler:
  enabled: true
  check_interval: 300  # 5分钟检查一次
EOF
    
    log_success "开发配置文件创建完成"
}

# 显示使用说明
show_usage() {
    echo -e "${GREEN}"
    echo "=========================================="
    echo "     HotStream 本地开发环境已就绪"
    echo "=========================================="
    echo -e "${NC}"
    
    echo -e "${BLUE}常用开发命令:${NC}"
    echo "1. 启动服务: python -m hotstream.cli start --config configs/hotstream-dev.yaml"
    echo "2. 测试搜索: python -m hotstream.cli search twitter \"AI\" --limit 10"
    echo "3. 监控账号: python -m hotstream.cli monitor --accounts elonmusk,openai"
    echo "4. 查看日志: tail -f logs/hotstream.log"
    echo "5. 停止服务: Ctrl+C"
    
    echo ""
    echo -e "${BLUE}测试Twitter数据获取:${NC}"
    echo "python -m hotstream.cli test-nitter elonmusk"
    
    echo ""
    echo -e "${BLUE}Web界面 (如果启用):${NC}"
    echo "http://localhost:8000"
    
    echo ""
    echo -e "${YELLOW}注意事项:${NC}"
    echo "- 使用开发配置文件: configs/hotstream-dev.yaml"
    echo "- 输出文件位于: output/"
    echo "- 日志文件位于: logs/"
    echo "- 虚拟环境已激活，可直接运行命令"
}

# 启动开发服务器
start_dev_server() {
    log_info "启动HotStream开发服务器..."
    
    # 检查端口是否被占用
    if lsof -i :8000 >/dev/null 2>&1; then
        log_warning "端口8000已被占用，将使用8001端口"
        export HOTSTREAM_PORT=8001
    fi
    
    # 启动服务
    python -m hotstream.cli start --config configs/hotstream-dev.yaml --dev
}

# 主函数
main() {
    echo -e "${GREEN}"
    echo "=========================================="
    echo "    HotStream 本地开发环境启动"
    echo "=========================================="
    echo -e "${NC}"
    
    # 检查是否在项目根目录
    if [ ! -f "requirements.txt" ] || [ ! -d "hotstream" ]; then
        log_error "请在项目根目录运行此脚本"
        exit 1
    fi
    
    # 询问启动模式
    echo "请选择启动模式:"
    echo "1) 快速启动服务 (默认)"
    echo "2) 仅设置环境"
    echo "3) 交互式测试"
    read -p "请输入选择 (1/2/3): " -n 1 -r
    echo
    
    # 基础环境设置
    check_python
    setup_venv
    create_dev_config
    
    case $REPLY in
        2)
            show_usage
            log_success "开发环境已准备就绪！运行上述命令开始开发"
            ;;
        3)
            show_usage
            log_info "进入交互式测试模式..."
            exec $SHELL
            ;;
        *)
            start_dev_server
            ;;
    esac
}

# 清理函数
cleanup() {
    log_info "正在清理..."
    # 在这里添加清理逻辑
    exit 0
}

# 设置信号处理
trap cleanup SIGINT SIGTERM

# 运行主函数
main "$@"