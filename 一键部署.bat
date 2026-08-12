@echo off
chcp 65001 >nul
title BidAgent-KB 一键部署向导

echo.
echo ==========================================
echo    BidAgent-KB 标书智能体 一键部署
echo ==========================================
echo.

:: 检查 Python
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3.8+
    echo        下载地址: https://www.python.org/downloads/
    echo        安装时请勾选 "Add Python to PATH"
    pause
    exit /b 1
)

:: 显示 Python 版本
echo [1/4] Python 检测通过:
python --version
echo.

:: 检查 Git
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo [提示] 未检测到 Git，将使用 ZIP 下载方式
    echo        如需 Git: https://git-scm.com/downloads
    echo.

    :: 下载 ZIP
    echo [2/4] 正在下载项目 ZIP 包...
    powershell -Command "Invoke-WebRequest -Uri 'https://github.com/tten3306879456/BidAgent-KB/archive/refs/heads/main.zip' -OutFile 'BidAgent-KB.zip'"
    if %errorlevel% neq 0 (
        echo [错误] 下载失败，请检查网络连接
        echo        或手动访问: https://github.com/tten3306879456/BidAgent-KB
        pause
        exit /b 1
    )

    echo [3/4] 解压中...
    powershell -Command "Expand-Archive -Path 'BidAgent-KB.zip' -DestinationPath '.' -Force"
    move "BidAgent-KB-main" "BidAgent-KB" >nul 2>&1
    del "BidAgent-KB.zip"

    cd BidAgent-KB
    echo.

) else (
    :: 使用 Git 克隆
    echo [2/4] Git 检测通过，正在克隆仓库...
    git clone https://github.com/tten3306879456/BidAgent-KB.git
    if %errorlevel% neq 0 (
        echo [错误] 克隆失败，请检查网络连接
        echo        或手动访问: https://github.com/tten3306879456/BidAgent-KB
        pause
        exit /b 1
    )
    cd BidAgent-KB
    echo.
)

:: 运行部署向导
echo [4/4] 启动部署向导...
echo ==========================================
echo.
python scripts/setup_wizard.py --quick --skip-venv

echo.
echo ==========================================
echo 部署完成！接下来可以:
echo   python scripts/kb_local_search.py "投标保证金"
echo   python scripts/channel_notify.py list
echo.
echo 详细文档: docs/部署指南.md
echo ==========================================
echo.
pause
