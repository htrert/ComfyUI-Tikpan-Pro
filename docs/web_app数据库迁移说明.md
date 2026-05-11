# web_app 数据库迁移与配置同步说明

这个项目里的 `web_app/data/tikpan.db` 是本机运行数据库，不应该直接提交到 Git。它里面可能包含用户余额、订单、生成记录、供应商 API Key、登录密钥等私有数据。

现在已经把“可以跨电脑同步的商业配置”拆成了可提交文件和脚本：

- `web_app/data/schema.sql`：数据库表结构。
- `web_app/data/seed.example.json`：脱敏后的默认业务配置，包含当前模型、字段、计费规则、供应商渠道骨架。
- `web_app/scripts/init_db.py`：新机器初始化数据库。
- `web_app/scripts/export_config.py`：从当前数据库导出可迁移配置。
- `web_app/scripts/import_config.py`：把导出的配置导入另一台电脑。

## 换电脑时怎么做

在新电脑拉取仓库后，进入 `ComfyUI-Tikpan-Pro` 目录，执行：

```powershell
python web_app/scripts/init_db.py
```

这会创建新的 `web_app/data/tikpan.db`，并导入 `seed.example.json` 里的模型、字段、计费和渠道配置。

## 从旧电脑导出后台配置

如果你在旧电脑后台改了模型字段、供应商渠道、计费规则，先执行：

```powershell
python web_app/scripts/export_config.py --out web_app/data/config.export.json
```

默认导出会自动脱敏：

- 供应商 `api_key` 会置空。
- `password`、`secret`、`token`、`api_key` 等敏感系统配置会置空。
- 不导出用户、订单、余额、生成记录、恢复记录、密码哈希。

把 `web_app/data/config.export.json` 复制到新电脑同一路径后执行：

```powershell
python web_app/scripts/import_config.py --in web_app/data/config.export.json
```

导入可以重复执行，不会重复插入同一个模型或字段。导入文件里的空 API Key 不会覆盖新电脑后台已经填写好的 API Key。

## 私有完整配置备份

如果只是你自己的两台电脑之间迁移，并且确认文件不会上传公开仓库，可以导出带密钥的私有备份：

```powershell
python web_app/scripts/export_config.py --include-secrets --out web_app/data/config.backup.json
```

`*.export.json`、`*.backup.json` 和 `config.local.json` 已经加入 `.gitignore`，正常不会被提交。

## 什么该提交，什么不该提交

应该提交：

- 表结构：`schema.sql`
- 脱敏默认配置：`seed.example.json`
- 脚本和文档
- Web 代码、节点代码、教程

不应该提交：

- `web_app/data/tikpan.db`
- `web_app/data/*.db-wal`
- `web_app/data/*.db-shm`
- `recovery/`
- 带真实密钥的 `config.backup.json`

这样处理之后，Git 负责同步“产品能力和商业配置骨架”，本地数据库负责保存“用户资产和运行记录”。
