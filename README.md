# ESL MQTT 模板服务器

## 项目简介

ESL MQTT 模板服务器是一个专为电子价签（Electronic Shelf Label）系统设计的模板管理和分发服务。该系统通过 MQTT 协议与 ESL 设备通信，提供模板文件的上传、管理和分发功能。

## 主要功能

- **MQTT 通信**: 支持与 ESL 设备的双向 MQTT 通信
- **模板管理**: 提供图形化界面管理模板文件
- **HTTP 服务**: 内置 HTTP 服务器用于模板文件分发
- **实时监控**: 实时显示通信日志和系统状态
- **跨平台支持**: 支持 Windows、Linux 等操作系统

## 系统要求

- Python 3.7 或更高版本
- 网络连接（用于 MQTT 和 HTTP 通信）

## 安装说明

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 运行程序

```bash
python main.py
```

## 使用指南

### 1. MQTT 连接配置

1. 启动程序后，在"MQTT Connection Settings"区域配置连接参数：
   - **Broker IP**: MQTT 服务器地址
   - **Port**: MQTT 服务器端口（默认 1883）
   - **Username**: 用户名（可选）
   - **Password**: 密码（可选）

2. 点击"Connect"按钮连接到 MQTT 服务器

### 2. 订阅和发布配置

- **订阅主题**: 建议使用 `esl/#` 监听所有 ESL 相关消息
- **发布主题**: 使用 `esl/server/data/{SHOP_ID}` 格式发送消息

### 3. 模板管理

- 使用右侧"Template File Manager"添加、删除和管理模板文件
- 支持 JSON 格式的模板文件
- 系统自动扫描 `resource` 目录中的模板文件

## API 接口

### HTTP 接口

系统提供以下 HTTP 接口：

- **POST** `/api/res/templ/loadtemple` - 加载指定模板
- **GET** `/api/res/templ/list` - 获取模板列表
- **GET** `/api/health` - 健康检查

### 模板请求示例

#### 1. 请求模板列表

发送到 MQTT 主题 `esl/server/data/{SHOP_ID}`:

```json
{
    "shop": "BY001",
    "data": {
        "tmpls": [
            {
                "name": "AES模板2.13T_06.json",
                "id": "1961431624180719617",
                "md5": "fcc5fdfd83486ff8e66f41d5691e0c1e"
            }
        ],
        "url": "http://192.168.1.1:8080/api/res/templ/loadtemple",
        "tid": "e166a1da-5961-4ad6-b68a-af154868de87"
    },
    "id": "96f80451-2eb1-4209-b176-d2627723be1b",
    "command": "tmpllist",
    "timestamp": 1760907539.474
}
```

#### 2. 写入标签数据

确认模板获取成功后，发送标签数据：

```json
{
    "command": "wtag",
    "data": [
        {
            "tag": 6597069775359,
            "tmpl": "AES模板2.13T",
            "model": "06",
            "checksum": "FCC5FDFD83486FF8E66F41D5691E0C1E",
            "forcefrash": 1,
            "value": {
                "GOODS_CODE": "00101",
                "GOODS_NAME": "2.13T",
                "F_01": "-1.00",
                "F_02": "PRODUCT_FRUIT",
                "F_03": "98.00",
                "F_04": "2.13T98798",
                "F_05": "98.00",
                "F_06": "98.00",
                "F_07": "-1.00",
                "F_08": "98.00",
                "F_09": "98",
                "F_10": "http://10.3.36.25:82/dev/file/download?id=1961436967577214978&Domain=http://localhost:81",
                "F_11": "98",
                "F_12": "<p>98</p>",
                "F_13": "kg",
                "F_14": "98",
                "F_15": "98",
                "F_16": "98",
                "F_17": "98",
                "F_18": "98"
            },
            "taskid": 74952,
            "token": 974731
        }
    ],
    "id": "5243dab4-bce0-46dd-9fb1-6b86b4d2f508",
    "timestamp": 1760968474.932,
    "shop": "BY001"
}
```

## 重要说明

- 每次发送消息时，`timestamp`、`tid`、`id`、`taskid`、`token` 等字段必须使用唯一值
- 模板文件必须放置在 `resource` 目录中
- HTTP 服务器默认监听端口 8080，支持跨域访问
- 系统支持自动 JSON 格式修复，兼容不同客户端的请求格式

## 故障排除

### 常见问题

1. **连接失败**: 检查 MQTT 服务器地址和端口是否正确
2. **模板加载失败**: 确认模板文件存在于 `resource` 目录中
3. **HTTP 请求失败**: 检查防火墙设置和网络连接

### 日志查看

程序运行时会在界面下方显示详细的活动日志，包括：
- MQTT 连接状态
- 消息收发记录
- HTTP 请求处理
- 错误信息和警告

## 技术支持

如需技术支持或有任何问题，请联系开发团队。

俗语版本：
使用方法！
输入ip端口，连接mqtt服务器！
输入订阅监听地址！esl/#
输入订阅发送地址！esl/server/data/BY001
填入json！
{
    "shop": "BY001",
    "data": {
        "tmpls": [
            {
                "name": "AES模板2.13T_06.json",
                "id": "1961431624180719617",
                "md5": "fcc5fdfd83486ff8e66f41d5691e0c1e"
            }
        ],
        "url": "http://192.168.1.1:8080/api/res/templ/loadtemple",
        "tid": "e166a1da-5961-4ad6-b68a-af154868de87"
    },
    "id": "96f80451-2eb1-4209-b176-d2627723be1b",
    "command": "tmpllist",
    "timestamp": 1760907539.474
}

其中每一次发送的timestamp，tid，id都需要每次都不同！
然后发送即可！
检查AP查看得到模板后！
发送新的json
{
    "command": "wtag",
    "data": [
        {
            "tag": 6597069775359,
            "tmpl": "AES模板2.13T",
            "model": "06",
            "checksum": "FCC5FDFD83486FF8E66F41D5691E0C1E",
            "forcefrash": 1,
            "value": {
                "GOODS_CODE": "00101",
                "GOODS_NAME": "2.13T",
                "F_01": "-1.00",
                "F_02": "PRODUCT_FRUIT",
                "F_03": "98.00",
                "F_04": "2.13T98798",
                "F_05": "98.00",
                "F_06": "98.00",
                "F_07": "-1.00",
                "F_08": "98.00",
                "F_09": "98",
                "F_10": "http://10.3.36.25:82/dev/file/download?id=1961436967577214978&Domain=http://localhost:81",
                "F_11": "98",
                "F_12": "<p>98</p>",
                "F_13": "kg",
                "F_14": "98",
                "F_15": "98",
                "F_16": "98",
                "F_17": "98",
                "F_18": "98"
            },
            "taskid": 74952,
            "token": 974731
        }
    ],
    "id": "5243dab4-bce0-46dd-9fb1-6b86b4d2f508",
    "timestamp": 1760968474.932,
    "shop": "BY001"
}
其中每一次发送的timestamp，taskid，id，token都需要每次都不同！
最后发送即可！即可检查AP是否成功刷新！这就是2.13T的刷新流程！
---

**版本**: 1.0  
**最后更新**: 2024年