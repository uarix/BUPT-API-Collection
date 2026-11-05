# 馆藏查询：期刊现刊与装订刊

[← 返回模块总览](README.md)

本文档描述期刊（连续出版物）相关的三个接口。它们均以 `rec_ctrl_id`（即检索结果中的 `recCtrlId`）为关联键，且只在详情页存在 `id="qikanInfos"` 时才需要调用。

- **鉴权**：均无
- **Content-Type**：`application/x-www-form-urlencoded; charset=UTF-8`
- **返回**：JSON

---

## 期刊现刊概况

- **上游地址**：`POST https://opac.bupt.edu.cn/qikanInfos.json`

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `rec_ctrl_id` | string | 是 | 期刊记录 ID |

### 返回字段（`data[]` 每项）

| 上游字段 | 说明 |
| --- | --- |
| `name` | 分馆/馆藏部门名称 |
| `libID` | 分馆 ID，供后续接口使用 |
| `curYear` | 当前年份 |
| `curCount` | 当前年现刊数量 |
| `lastYear` | 上一年份 |
| `lastCount` | 上一年现刊数量 |

### 请求示例

```
POST /qikanInfos.json
Referer: https://opac.bupt.edu.cn/bookInfo_{rec_ctrl_id}.html

rec_ctrl_id=1198001703
```

### 响应示例（节选）

```json
{
  "result": { "code": 0, "msg": "" },
  "data": [
    {
      "name": "本部期刊阅览室",
      "libID": "L01",
      "curYear": "2026",
      "curCount": 12,
      "lastYear": "2025",
      "lastCount": 12
    }
  ]
}
```

---

## 期刊现刊记录

- **上游地址**：`POST https://opac.bupt.edu.cn/serialnobinding.json`

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `rec_ctrl_id` | string | 是 | 期刊记录 ID |
| `library_id` | string | 是 | 分馆 ID，取自现刊概况的 `libID` |
| `s_year` | string | 是 | 年份，取自现刊概况的 `curYear` 或 `lastYear` |

> **注意**：仅对现刊概况中数量（`curCount` / `lastCount`）大于 0 的年份发起查询，否则无意义。

### 返回字段（`data[]` 每项）

| 上游字段 | 客户端字段 | 说明 |
| --- | --- | --- |
| `year` | `year` | 年份 |
| `volume` | `volume` | 卷 |
| `issue` | `issue` | 期号 |
| `codeDesc` | `status` | 状态 |
| `shelfDistribute` | `shelf_number` | 排架号 |
| `departmentName` | `department` | 馆藏部门 |

### 请求示例

```
POST /serialnobinding.json
Referer: https://opac.bupt.edu.cn/bookInfo_1198001703.html

rec_ctrl_id=1198001703&library_id=L01&s_year=2026
```

### 响应示例（节选）

```json
{
  "result": { "code": 0, "msg": "" },
  "data": [
    {
      "year": "2026",
      "volume": "40",
      "issue": "3",
      "codeDesc": "在架",
      "shelfDistribute": "J-12",
      "departmentName": "本部期刊阅览室"
    }
  ]
}
```

---

## 期刊装订馆藏

- **上游地址**：`POST https://opac.bupt.edu.cn/bindings.json`

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `rec_ctrl_id` | string | 是 | 期刊记录 ID |

### 返回字段（`data[]` 每项）

| 上游字段 | 客户端字段 | 说明 |
| --- | --- | --- |
| `departmentName` | `department` | 馆藏部门 |
| `bookBarcode` | `barcode` | 装订刊条码 |
| `bookSearchNo` | `call_number` | 索书号 |
| `accessNo` | `accession_number` | 登录号 |
| `issus` | `volume` | 卷期 |
| `circul` | `status` | 流通状态 |

> 期刊的装订刊在客户端输出中替换 `holdings` 字段；`navigation_url` 为空，`navigation_is_private_network` 为 `false`（期刊页面未提供架位导航链接）。

### 请求示例

```
POST /bindings.json
Referer: https://opac.bupt.edu.cn/bookInfo_1198001703.html

rec_ctrl_id=1198001703
```

### 响应示例（节选）

```json
{
  "result": { "code": 0, "msg": "" },
  "data": [
    {
      "departmentName": "本部期刊阅览室",
      "bookBarcode": "B7654321",
      "bookSearchNo": "TP3/xxx",
      "accessNo": "7654321",
      "issus": "2025, no.1-6",
      "circul": "可借"
    }
  ]
}
```

---

## 调用顺序

期刊详情页的处理顺序：

1. `GET /bookInfo_{recCtrlId}.html`，确认存在 `id="qikanInfos"`
2. `POST /qikanInfos.json` 获取分馆及年份概况
3. 对每个分馆、每个数量 > 0 的年份，`POST /serialnobinding.json` 获取现刊记录
4. `POST /bindings.json` 获取装订刊馆藏

客户端最终输出 `periodical_current`（第 2 步）与 `current_issues`（第 3 步），`holdings` 为第 4 步结果。

---

[← 返回模块总览](README.md)
