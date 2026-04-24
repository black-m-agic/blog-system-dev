# 博客系统安全加固文档

## 📋 安全改进概述

本文档详细记录了博客系统的安全加固措施和最佳实践。

## 🔒 已实施的安全措施

### 1. **API密钥加密存储**
- **文件**: `utils/encryption.py`
- **功能**:
  - 使用 Fernet 对称加密算法
  - API密钥不再明文存储在 Session 中
  - 使用 SECRET_KEY 派生加密密钥
  - 自动生成加密密钥（如果没有设置）
- **使用场景**: AI API密钥安全存储

### 2. **请求速率限制**
- **文件**: `utils/security.py`
- **功能**:
  - 防止暴力破解攻击
  - 防止 API 滥用
  - 按用户/IP 分别限制
  - 自动清理过期记录
- **限制策略**:
  - 登录: 10次/分钟
  - 注册: 5次/分钟
  - AI聊天: 30次/分钟
  - 发表文章: 10次/分钟
  - 评论: 20次/分钟

### 3. **输入验证与XSS防护**
- **文件**: `utils/security.py`
- **功能**:
  - 用户名验证（长度、格式）
  - 邮箱格式验证
  - 文章标题/内容长度限制
  - 评论内容长度限制
  - HTML清理（使用 Bleach）
- **允许的HTML标签**: `a`, `abbr`, `acronym`, `b`, `blockquote`, `code`, `em`, `i`, `li`, `ol`, `strong`, `ul`, `br`, `p`, `h1`, `h2`, `h3`, `h4`, `h5`, `h6`, `pre`, `div`, `span`

### 4. **安全响应头**
- **实现位置**: `app.py` -> `add_security_headers()`
- **已添加的安全头**:
  - `X-Content-Type-Options: nosniff` - 防止 MIME 类型嗅探
  - `X-Frame-Options: SAMEORIGIN` - 防止点击劫持
  - `X-XSS-Protection: 1; mode=block` - 启用 XSS 过滤器
  - `Content-Security-Policy` - 内容安全策略
  - `Referrer-Policy: strict-origin-when-cross-origin` - 控制引用信息
  - `Permissions-Policy` - 限制 API 访问

### 5. **Session安全配置**
- **实现位置**: `app.py`
- **配置项**:
  - `SESSION_COOKIE_HTTPONLY = True` - 防止 JavaScript 访问 Cookie
  - `SESSION_COOKIE_SAMESITE = 'Lax'` - 防止 CSRF 攻击
  - `SESSION_COOKIE_SECURE` - HTTPS 时启用（生产环境）
  - `PERMANENT_SESSION_LIFETIME = 7天` - 会话过期时间

### 6. **SECRET_KEY安全处理**
- **实现位置**: `app.py`
- **功能**:
  - 从环境变量读取
  - 自动生成强密钥（如果没有设置）
  - 生产环境警告提示
- **生成方法**: `os.urandom(32).hex()`

### 7. **生产环境保护**
- **实现位置**: `app.py`
- **功能**:
  - 自动禁用 `debug` 模式
  - 禁用 `allow_unsafe_werkzeug`
  - 环境变量控制 (ENVIRONMENT=production)

### 8. **安全日志记录**
- **实现位置**: `utils/security.py` -> `log_security_event()`
- **记录的事件**:
  - 登录成功/失败
  - 注册成功
  - 安全设置更新
  - 评论添加
  - 速率限制触发
  - 无效输入

## 📁 新增文件清单

```
blog-system/
├── utils/
│   ├── security.py       # 安全工具模块
│   └── encryption.py     # 加密工具模块
├── SECURITY.md           # 本文档
└── .env.example          # 环境变量模板
```

## 🔧 部署安全检查清单

### 部署前必做

- [ ] **设置强SECRET_KEY**
  ```bash
  # 生成安全密钥
  python -c "import os; print(os.urandom(32).hex())"
  ```
  
- [ ] **创建.env文件**
  ```env
  ENVIRONMENT=production
  SECRET_KEY=your_generated_secure_key_here
  ```

- [ ] **使用HTTPS**
  - 配置 SSL/TLS 证书
  - 强制 HTTPS 重定向

- [ ] **安装依赖**
  ```bash
  pip install -r requirements.txt
  ```

### 生产环境配置

```env
ENVIRONMENT=production
SECRET_KEY=your_very_secure_random_secret_key
```

## 🚨 安全最佳实践

### 1. **密码安全**
- 使用强密码（已在 `validate_password_strength` 中实现）
- 密码使用 `werkzeug.security` 的哈希算法存储（已实现）
- 不要重用密码

### 2. **服务器安全**
- 定期更新系统和依赖库
- 使用防火墙限制访问
- 配置日志监控和警报
- 定期备份数据库

### 3. **代码安全**
- 不要在代码中硬编码密钥
- 不要将 `.env` 文件提交到 Git
- 定期进行安全审计
- 使用代码扫描工具

### 4. **用户数据保护**
- 最小化收集用户数据
- 对敏感数据进行加密
- 提供数据删除选项
- 遵守数据保护法规

## 📊 安全漏洞风险评估

| 风险类型 | 严重程度 | 防护措施 | 状态 |
|---------|---------|---------|------|
| SQL注入 | 高 | 使用ORM (SQLAlchemy) | ✅ 已实现 |
| XSS攻击 | 高 | 输入验证 + HTML清理 | ✅ 已实现 |
| CSRF攻击 | 高 | CSRF保护 + SameSite Cookie | ✅ 已实现 |
| 暴力破解 | 中 | 速率限制 | ✅ 已实现 |
| 密钥泄露 | 高 | 加密存储 + 环境变量 | ✅ 已实现 |
| 点击劫持 | 中 | X-Frame-Options | ✅ 已实现 |
| Session劫持 | 中 | HTTPOnly + Secure Cookie | ✅ 已实现 |

## 🔍 安全测试建议

### 1. **自动化测试**
```bash
# 使用 OWASP ZAP 进行扫描
# 使用 Nikto 进行漏洞扫描
```

### 2. **手动测试清单**
- [ ] 测试 SQL 注入
- [ ] 测试 XSS 攻击
- [ ] 测试 CSRF 攻击
- [ ] 测试速率限制
- [ ] 测试会话安全
- [ ] 测试访问控制

## 📞 安全问题报告

如果发现安全漏洞，请按以下方式报告：

1. 描述问题细节
2. 提供复现步骤
3. 说明影响范围
4. 建议修复方案（如果有）

## 📚 参考资源

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Flask 安全最佳实践](https://flask.palletsprojects.com/en/latest/security/)
- [MDN Web 安全](https://developer.mozilla.org/zh-CN/docs/Web/Security)

## 🔄 版本历史

| 版本 | 日期 | 改动 |
|------|------|------|
| 1.0 | 2026-04-24 | 初始安全加固版本 |

---

**最后更新**: 2026-04-24
