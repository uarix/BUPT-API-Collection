# 图书馆系统 API

北京邮电大学图书馆 OPAC（联机公共目录查询系统）的公开接口整理。

- **站点**：<https://opac.bupt.edu.cn>
- **性质**：网页前端实际调用的公开接口，**并非馆方承诺稳定的开放 API**，随时可能变更
- **范围**：仅收录只读的书目查询类接口；
- **鉴权**：本目录所有接口均为匿名可访问，无需登录

## ⚠️ 使用声明

- 仅供学习和技术研究，严禁用于非法用途
- 请遵守学校网络使用准则
- 上游请求间隔建议 **≥ 1 秒**，禁止高并发批量抓取或遍历全馆记录
- 馆藏状态实时变化，请以馆方页面为准

## 接口索引

| 接口 | 方法 | 用途 | 鉴权 | 文档 |
| --- | --- | --- | --- | --- |
| `/search-full-result.json` | POST | 书刊检索 | 无（需同站 Referer） | [opac-search.md](opac-search.md) |
| `/bookInfo_{recCtrlId}.html` | GET | 图书/期刊详情 | 无 | [opac-search.md](opac-search.md) |
| `/qikanInfos.json` | POST | 期刊现刊概况 | 无 | [opac-holdings.md](opac-holdings.md) |
| `/serialnobinding.json` | POST | 期刊现刊记录 | 无 | [opac-holdings.md](opac-holdings.md) |
| `/bindings.json` | POST | 期刊装订馆藏 | 无 | [opac-holdings.md](opac-holdings.md) |

## 通用约定

- **Base URL**：`https://opac.bupt.edu.cn`
- **字符编码**：UTF-8
- **Referer**：检索类接口要求携带同站 `Referer`（如 `https://opac.bupt.edu.cn/search-full-result.html`），否则可能被拒绝
- **Content-Type**（POST）：`application/x-www-form-urlencoded; charset=UTF-8`
- **返回格式**：JSON 接口统一为 `{"result": {"code": 0, "msg": "..."}, "data": ...}`，`code == 0` 表示成功
- **限速**：客户端进程内上游请求间隔至少 1 秒

## 参考实现

本目录文档对应的参考客户端见仓库根目录 `bupt_opac.py`（Python 3.10+，仅依赖标准库），提供命令行与本地只读 HTTP API。
