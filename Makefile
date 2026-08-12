# 标书智能体专家系统 — Makefile
# 提供一键命令简化部署和日常操作
#
# 使用方式:
#   make setup       — 交互式部署向导
#   make quick       — 快速部署(全默认值)
#   make check       — 检查环境
#   make test        — 运行验证测试
#   make search      — 搜索知识库 (make search Q="投标保证金")
#   make console     — 启动管理控制台(覆盖度分析+上传+配置)
#   make coverage    — 输出知识库覆盖度分析报告
#   make channels    — 列出已配置渠道
#   make test-channel — 测试渠道连接 (make test-channel C=feishu)
#   make send        — 发送消息 (make send MSG="测试消息")
#   make update-channel — 更新渠道凭证 (make update-channel C=feishu PAIRS="FEISHU_WEBHOOK_URL=https://...")
#   make clean       — 清理临时文件
#   make help        — 显示帮助

# ============================================================
# 变量
# ============================================================
PYTHON ?= python
SCRIPTS = scripts

# ============================================================
# 部署命令
# ============================================================

.PHONY: setup quick check

## 交互式部署向导
setup:
	$(PYTHON) $(SCRIPTS)/setup_wizard.py

## 快速部署(全默认值, 跳过虚拟环境)
quick:
	$(PYTHON) $(SCRIPTS)/setup_wizard.py --quick --skip-venv

## 检查环境(不部署)
check:
	$(PYTHON) $(SCRIPTS)/setup_wizard.py --check

# ============================================================
# 知识库命令
# ============================================================

.PHONY: kb-init kb-setup search

## 初始化本地知识库目录
kb-init:
	$(PYTHON) $(SCRIPTS)/kb_init.py ./kb_data

## 初始化知识库后端(默认local_search)
kb-setup:
	$(PYTHON) $(SCRIPTS)/kb_setup.py --backend local_search --quick

## 搜索知识库 (用法: make search Q="关键词")
search:
	@if [ -z "$(Q)" ]; then echo "用法: make search Q=\"关键词\""; exit 1; fi
	$(PYTHON) $(SCRIPTS)/kb_local_search.py "$(Q)"

# ============================================================
# 管理控制台命令
# ============================================================

.PHONY: console coverage

## 启动管理控制台(覆盖度分析+文件上传+参数配置)
console:
	$(PYTHON) $(SCRIPTS)/kb_console.py

## 输出知识库覆盖度分析报告(不启动服务器)
coverage:
	$(PYTHON) $(SCRIPTS)/kb_console.py --check

# ============================================================
# 渠道命令
# ============================================================

.PHONY: channels test-channel send update-channel

## 列出已配置的渠道
channels:
	$(PYTHON) $(SCRIPTS)/channel_notify.py list

## 测试渠道连接 (用法: make test-channel C=feishu)
test-channel:
	@if [ -z "$(C)" ]; then \
		$(PYTHON) $(SCRIPTS)/channel_notify.py test; \
	else \
		$(PYTHON) $(SCRIPTS)/channel_notify.py test $(C); \
	fi

## 发送消息到所有渠道 (用法: make send MSG="消息内容")
send:
	@if [ -z "$(MSG)" ]; then echo "用法: make send MSG=\"消息内容\""; exit 1; fi
	$(PYTHON) $(SCRIPTS)/channel_notify.py send "$(MSG)"

## 更新渠道凭证 (用法: make update-channel C=feishu PAIRS="KEY=val KEY2=val2")
update-channel:
	@if [ -z "$(C)" ] || [ -z "$(PAIRS)" ]; then \
		echo "用法: make update-channel C=feishu PAIRS=\"FEISHU_WEBHOOK_URL=https://...\""; exit 1; \
	fi
	$(PYTHON) $(SCRIPTS)/channel_notify.py update $(C) $(PAIRS) --save

# ============================================================
# 验证命令
# ============================================================

.PHONY: test verify

## 运行验证测试
test verify:
	@echo "=== 环境检查 ==="
	$(PYTHON) $(SCRIPTS)/setup_wizard.py --check
	@echo ""
	@echo "=== 知识库搜索测试 ==="
	$(PYTHON) $(SCRIPTS)/kb_local_search.py "投标保证金" || true
	@echo ""
	@echo "=== 渠道状态 ==="
	$(PYTHON) $(SCRIPTS)/channel_notify.py list || true

# ============================================================
# 清理命令
# ============================================================

.PHONY: clean clean-all

## 清理临时文件
clean:
	@find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.pyc" -delete 2>/dev/null || true
	@find . -name ".tmp_*" -delete 2>/dev/null || true
	@rm -f scripts/_test*.py scripts/_test*.env 2>/dev/null || true
	@echo "临时文件已清理"

## 深度清理(含虚拟环境和知识库数据)
clean-all: clean
	@rm -rf venv/ .venv/ 2>/dev/null || true
	@rm -rf chroma_db/ 2>/dev/null || true
	@rm -rf kb_data/ 2>/dev/null || true
	@echo "深度清理完成(venv/chroma_db/kb_data 已删除)"

# ============================================================
# 帮助
# ============================================================

.PHONY: help

## 显示帮助
help:
	@echo "标书智能体专家系统 — 命令列表"
	@echo ""
	@echo "部署命令:"
	@echo "  make setup        交互式部署向导"
	@echo "  make quick        快速部署(全默认值)"
	@echo "  make check        检查环境"
	@echo ""
	@echo "知识库命令:"
	@echo "  make kb-init      初始化本地知识库目录"
	@echo "  make kb-setup     初始化知识库后端"
	@echo "  make search Q=\"关键词\"  搜索知识库"
	@echo "  make console      启动管理控制台(浏览器)"
	@echo "  make coverage     输出覆盖度分析报告"
	@echo ""
	@echo "渠道命令:"
	@echo "  make channels     列出已配置渠道"
	@echo "  make test-channel C=feishu  测试渠道(不指定C则测试全部)"
	@echo "  make send MSG=\"消息\"  发送消息到所有渠道"
	@echo "  make update-channel C=feishu PAIRS=\"KEY=val\"  更新渠道凭证"
	@echo ""
	@echo "其他:"
	@echo "  make test         运行验证测试"
	@echo "  make clean        清理临时文件"
	@echo "  make clean-all    深度清理(含venv/kb_data)"
	@echo "  make help         显示此帮助"
