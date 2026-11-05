# 馆藏查询：检索与详情

[← 返回模块总览](README.md)

本文档描述 OPAC 的书刊检索接口与书刊详情页。

---

## 书刊检索

- **上游地址**：`POST https://opac.bupt.edu.cn/search-full-result.json`
- **鉴权**：无。需携带同站 `Referer`（如 `https://opac.bupt.edu.cn/search-full-result.html`）
- **Content-Type**：`application/x-www-form-urlencoded; charset=UTF-8`
- **返回**：JSON

### 请求参数

| 参数 | 类型 | 必填 | 说明 | 取值 |
| --- | --- | --- | --- | --- |
| `keyword` | string | 是 | 检索词 | 1–200 字符 |
| `solrType` | string | 是 | 检索字段 | `TITLE` / `AUTHOR` / `PUBDATE` / `PUBLISHER` / `ISN_SHOW` / `SUBJECT` |
| `xiaoqu` | string | 是 | 校区 | `all`（全部）/ `A01`（本部）/ `A02`（宏福）/ `A03`（沙河） |
| `pageNo` | string | 是 | 页码 | 1–1000 |
| `pageSize` | string | 是 | 每页条数 | `10` / `20` / `30` / `50` / `100` |
| `classSearch` | string | 是 | 固定值 | `"0"` |
| `searchPrecision` | string | 是 | 固定值 | `""` |

字段映射（客户端友好名 → 上游 `solrType`）：

| 客户端字段 | 上游 solrType | 含义 |
| --- | --- | --- |
| `title` | `TITLE` | 题名 |
| `author` | `AUTHOR` | 责任者 |
| `year` | `PUBDATE` | 出版年 |
| `publisher` | `PUBLISHER` | 出版社 |
| `isbn` | `ISN_SHOW` | 标准号（ISBN 或 ISSN） |
| `subject` | `SUBJECT` | 主题词 |

### 返回结构

顶层字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `result.code` | int | `0` 表示成功 |
| `result.msg` | string | 错误信息 |
| `total` | int | 命中总数 |
| `totalPage` | int | 总页数 |
| `data` | array | 书目记录列表 |

`data[]` 每项字段：

| 上游字段 | 类型 | 说明 |
| --- | --- | --- |
| `recCtrlId` | string | 记录 ID，用于详情页 |
| `title` | string | 题名 |
| `authors` | string | 责任者 |
| `publisher` | string | 出版社 |
| `pubdateDate` | string | 出版年 |
| `isn` | string | 标准号（ISBN/ISSN） |
| `bookSearchNo` | string | 索书号 |
| `guancangCount` | int | 馆藏总数 |
| `kejieCount` | int | 可借数量 |

### 请求示例

```
POST /search-full-result.json
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
Referer: https://opac.bupt.edu.cn/search-full-result.html

keyword=机器学习&solrType=TITLE&xiaoqu=all&pageNo=1&pageSize=20&classSearch=0&searchPrecision=
```

### 响应示例（节选）

```json
{
  "result": { "code": 0, "msg": "" },
  "total": 128,
  "totalPage": 7,
  "data": [
    {
      "recCtrlId": "01h0329633",
      "title": "机器学习",
      "authors": "周志华著",
      "publisher": "清华大学出版社",
      "pubdateDate": "2016",
      "isn": "978-7-302-42328-7",
      "bookSearchNo": "TP181/Z63",
      "guancangCount": 5,
      "kejieCount": 2
    }
  ]
}
```

### 备注

- “标准号”（`ISN_SHOW`）同时覆盖 ISBN 与 ISSN；客户端统一输出为 `isbn_issn`。
- 返回字段中 `guancangCount` / `kejieCount` 为实时馆藏统计，可能变化。

---

## 书刊详情

- **上游地址**：`GET https://opac.bupt.edu.cn/bookInfo_{recCtrlId}.html`
- **鉴权**：无
- **返回**：HTML（需从 HTML 中解析书目字段与馆藏表）

### 路径参数

| 参数 | 说明 |
| --- | --- |
| `recCtrlId` | 检索结果中的 `recCtrlId`，仅含字母数字，长度 ≤ 40 |

### 解析内容

**书目字段**：从页面段落中按标签提取。

| 页面标签 | 客户端字段 | 说明 |
| --- | --- | --- |
| `ISBN/ISSN` | `isbn_issn` | 标准号 |
| `出版` | `publication` | 出版信息 |
| `责任者` | `responsibility` | 责任者 |
| `中图分类号` | `classification` | 分类号 |
| `载体形态` | `physical_description` | 载体形态 |
| `并列题名` | `parallel_title` | 并列题名 |
| `价格` | `price` | 价格 |

**馆藏表**：页面中 `tbody#guancanglist` 表格，列含义：

| 列名 | 客户端字段 | 说明 |
| --- | --- | --- |
| 馆藏部门 | `department` | 收藏部门 |
| 图书条码 | `barcode` | 条码号 |
| 索书号 | `call_number` | 索书号 |
| 登录号 | `accession_number` | 登录号 |
| 卷期 | `volume` | 卷期 |
| 状态 | `status` | 流通状态 |
| 架位导航 | `navigation_url` | 架位导航链接（见下方说明） |

### 架位导航说明

架位导航链接由馆方页面提供。**当前样本指向 `10.x.x.x` 内网地址**，外网能否访问取决于使用者网络环境。客户端原样返回该链接，并附带布尔字段 `navigation_is_private_network` 标识是否内网地址。

### 请求示例

```
GET /bookInfo_01h0329633.html
```

### 响应示例（客户端输出，节选）

```json
{
  "id": "01h0329633",
  "title": "机器学习",
  "isbn_issn": "978-7-302-42328-7",
  "publication": "北京: 清华大学出版社, 2016",
  "responsibility": "周志华著",
  "classification": "TP181",
  "holdings": [
    {
      "department": "本部中文图书借阅室",
      "barcode": "A1234567",
      "call_number": "TP181/Z63",
      "accession_number": "1234567",
      "volume": "",
      "status": "可借",
      "navigation_url": "http://10.x.x.x/...",
      "navigation_is_private_network": true
    }
  ],
  "detail_url": "https://opac.bupt.edu.cn/bookInfo_01h0329633.html"
}
```

### 期刊记录

若详情页包含 `id="qikanInfos"` 元素，则该记录为期刊，客户端会额外请求期刊相关接口，返回 `periodical_current` 与 `current_issues`，并将 `holdings` 替换为装订刊数据。详见 [opac-holdings.md](opac-holdings.md)。

---

[← 返回模块总览](README.md)
