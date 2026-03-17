# Contributing to LambChat

感谢你有兴趣为 LambChat 做贡献！🎉

Thank you for your interest in contributing to LambChat! 🎉

## 🌟 如何贡献

### 报告 Bug

如果你发现了 bug，请通过 [GitHub Issues](https://github.com/Yanyutin753/LambChat/issues) 提交报告。

提交 bug 报告时，请包含：

1. **清晰的标题** - 简要描述问题
2. **复现步骤** - 详细说明如何重现问题
3. **预期行为** - 你期望发生什么
4. **实际行为** - 实际发生了什么
5. **环境信息** - 操作系统、Python 版本、Node.js 版本等
6. **截图** - 如果适用，添加截图帮助解释问题

### 建议新功能

我们欢迎新功能建议！请在 Issue 中详细描述：

1. 功能描述
2. 使用场景
3. 预期效果

### 提交代码

1. **Fork 仓库**
   ```bash
   git clone https://github.com/Yanyutin753/LambChat.git
   cd LambChat
   ```

2. **创建分支**
   ```bash
   git checkout -b feature/your-feature-name
   # 或
   git checkout -b fix/your-bug-fix
   ```

3. **安装开发依赖**
   ```bash
   # 后端
   make install
   
   # 前端
   cd frontend && npm install
   ```

4. **进行更改**
   - 遵循现有的代码风格
   - 添加必要的测试
   - 更新相关文档

5. **运行测试**
   ```bash
   make test
   make lint
   ```

6. **提交更改**
   ```bash
   git add .
   git commit -m "feat: 添加新功能描述"
   # 或
   git commit -m "fix: 修复问题描述"
   ```

7. **推送并创建 PR**
   ```bash
   git push origin feature/your-feature-name
   ```

## 📝 代码规范

### Python

- 使用 Python 3.12+
- 遵循 PEP 8 规范
- 使用 `ruff` 进行代码格式化
- 使用 `mypy` 进行类型检查

### TypeScript/React

- 使用 TypeScript
- 遵循 ESLint 规则
- 使用函数组件和 Hooks

### 提交信息规范

遵循 [Conventional Commits](https://www.conventionalcommits.org/)：

- `feat:` 新功能
- `fix:` Bug 修复
- `docs:` 文档更新
- `style:` 代码格式调整
- `refactor:` 代码重构
- `test:` 测试相关
- `chore:` 构建/工具链相关

## 🔒 安全问题

如果你发现安全漏洞，请**不要**在公开的 Issue 中报告。

请发送邮件至安全团队，我们会尽快处理。

## 📄 许可证

提交代码即表示你同意你的贡献将根据 MIT 许可证授权。

---

再次感谢你的贡献！❤️
