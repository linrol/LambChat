# Security Policy

## 安全策略

### 支持的版本

我们目前为以下版本提供安全更新：

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

### 报告安全漏洞

如果你发现安全漏洞，请**不要**在公开的 GitHub Issue 中报告。

请通过以下方式报告：

1. **GitHub Security Advisories** - 使用 [GitHub 的安全公告功能](https://github.com/Yanyutin753/LambChat/security/advisories/new)
2. **邮件** - 发送详细信息到项目维护者

报告时请包含：

- 漏洞类型（如 XSS、SQL 注入、CSRF 等）
- 复现步骤
- 影响范围
- 可能的修复建议

我们承诺：

- 在 48 小时内确认收到报告
- 在 7 天内提供初步评估
- 修复后及时发布安全公告

### 安全最佳实践

部署 LambChat 时，请确保：

1. **环境变量** - 不要在代码中硬编码敏感信息
2. **HTTPS** - 生产环境必须使用 HTTPS
3. **数据库** - 使用强密码并限制访问
4. **JWT Secret** - 使用足够强度的随机密钥
5. **定期更新** - 及时更新依赖包

### 致谢

感谢所有报告安全问题的贡献者！
